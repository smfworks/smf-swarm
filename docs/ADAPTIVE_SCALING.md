# Swarm Resource Profiler Design Document

> **Status:** Draft | **Target:** AetherSim / SMF-Swarm v1.1 | **Date:** 2026-04-23
>
> The purpose of this document is to specify how SMF Swarm auto-detects
> host hardware, calculates safe operational envelopes for agent swarms,
> presents those profiles back to the user for a **final human choice**,
> and persists that choice as the active configuration.

---

## 1. Problem Statement

SMF Predict ships as **packaged software** (Model A). It runs on
hardware from a Chromebook-class machine (4 GB RAM, no GPU) to a
developer workstation (128 GB RAM, 48 GB VRAM). Running a 20-agent,
400-step prediction on 4 GB RAM will OOM, crash, and produce a bad
user experience. But locking every installation to the 8 GB baseline
wastes the predictive power available on better hardware.

The solution: **hardware-aware adaptive scaling with user override**.

1. SMF Swarm detects what is available.
2. It computes a set of safe operating profiles.
3. It **recommends the best profile** but **asks the user** before
   locking it in.
4. The user can choose a smaller profile for faster runs, or a larger
   one if they understand the tradeoff.
5. The choice is persisted in the config — so every subsequent run
   uses the same profile until the user reconfigures.

---

## 2. Core Principles

### 2.1 Never Crash by Default
The auto-detected **recommended** profile must have a safety margin.
If we detect 32 GB, we recommend a profile that uses no more than
~24 GB (`0.75 × total`). The user can manually opt into higher if
they want to push the envelope, but the default should never OOM.

### 2.2 User Is Sovereign
The profiler is advisory. The user may choose:
- A profile *smaller* than recommended (fast test runs)
- A profile *larger* than recommended (maximum predictive depth)
- A custom override (advanced users)
- "Lock" a profile so it survives across sessions

### 2.3 Transparent and Auditable
Every profile explains, in plain terms, what tradeoff the user is
making:
- How many agents
- How many reasoning steps per agent
- Which LLM model
- Estimated wall-clock time
- Memory headroom remaining

### 2.4 Portable Across Architectures
Detection must work on:
- Linux (primary — the current Tailscale target)
- macOS (developer workstations)
- Windows (corporate laptops)

Without adding heavy dependencies. Use stdlib + lightweight
cross-platform packages (`psutil`, optionally `GPUtil`).

---

## 3. Profile Tiers

Each profile is a named bundle of swarm parameters. The user can
select any profile that does not exceed their hardware.

| Profile | Name | RAM Min | RAM Target | Agents | Steps/Agent | LLM | Use Case |
|:--------|:-----|:--------|:-----------|:-------|:------------|:----|:---------|
| `essential` | Barebones | 4 GB | 6 GB | 3 | 20 | qwen2.5:3b | Quick checks, small devices |
| `compact` | Compact | 6 GB | 8 GB | 5 | 50 | qwen2.5:7b | Default baseline, 8 GB laptops |
| `balanced` | Balanced | 8 GB | 12 GB | 8 | 100 | qwen2.5:7b | Standard predictions |
| `deep` | Deep Analysis | 16 GB | 20 GB | 12 | 200 | qwen2.5:14b | Serious analysis |
| `ensemble` | Large Ensemble | 32 GB | 36 GB | 20 | 400 | qwen2.5:32b | Maximum predictive depth |
| `cloud` | Cloud-Scale | 64 GB | 80 GB | 40 | 800 | qwen2.5:72b / api-hosted | Institutional deployments |

### Memory Model

Per-agent memory is roughly:
```
memory_per_agent ≈ model_size × conversation_depth

# Example: qwen2.5:32b at 8K context ≈ 32 GB model + ~2 GB context per agent
# With 20 agents = ~64 GB RAM minimum
```

In practice, with shared-model loading (Ollama caches), the numbers
above are conservative since models are loaded once.

---

## 4. Detection Algorithm

### Step 1: Hardware Inventory

```python
def detect_hardware() -> HardwareProfile:
    return HardwareProfile(
        total_ram_gb = psutil.virtual_memory().total / (1024**3),
        available_ram_gb = psutil.virtual_memory().available / (1024**3),
        vram_gb = detect_gpu_vram(),
        cpu_cores = psutil.cpu_count(logical=True),
        has_gpu = detect_gpu_vram() is not None,
    )
```

GPU detection (graceful fallback on failure):
```python
def detect_gpu_vram() -> float | None:
    try:
        import GPUtil
        gpus = GPUtil.getGPUs()
        return max(g.memoryTotal for g in gpus) / 1024  # GB
    except Exception:
        # Secondary detection for nvidia-smi
        return detect_nvidia_vram() or detect_apple_metal_vram()
```

### Step 2: Capability Score

Map raw hardware into a single ordinal score:

```python
def compute_capability(hw: HardwareProfile) -> CapabilityScore:
    ram_score = hw.total_ram_gb * 1.0
    vram_score = (hw.vram_gb or 0) * 2.5  # VRAM more valuable
    core_score = hw.cpu_cores * 0.5
    total = ram_score + vram_score + core_score
    return CapabilityScore(total=total, ram=ram_score, vram=vram_score)
```

### Step 3: Available Profiles

Filter the profile registry — only show profiles where `ram_target`
does not exceed `hw.total_ram_gb * safety_margin`.

Default safety margin: `0.75` (75% of total RAM).

```python
def filter_available_profiles(hw: HardwareProfile) -> list[SwarmProfile]:
    max_safe = hw.total_ram_gb * SAFETY_MARGIN
    return [p for p in ALL_PROFILES if p.ram_target <= max_safe]
```

### Step 4: Recommendation

Select the **highest** available profile as the default recommendation:

```python
def recommend_profile(available: list[SwarmProfile]) -> SwarmProfile:
    if not available:
        return ESSENTIAL_PROFILE  # Barebones fallback
    return max(available, key=lambda p: p.priority)
```

### Step 5: User Choice

Display all available profiles, **highlight the recommended one**, and
prompt. See §6 for the prompt format.

---

## 5. Profile Schema (YAML)

```yaml
# ~/.config/smf-swarm/config.yaml (excerpt after profiling)
swarm:
  profile: balanced
  profile_locked: true  # user must --force-reprofile to reset
  hardware_snapshot:
    detected_at: "2026-04-23T06:33:00Z"
    total_ram_gb: 31.2
    available_ram_gb: 22.1
    vram_gb: null
    cpu_cores: 8
    os: "Ubuntu 22.04"

  # Profile-derived overrides (can be manually edited)
  social_agents: 8
  social_rounds: 4
  debaters: 3
  debate_rounds: 2
  max_reasoning_steps: 100
  llm_model: "qwen2.5:7b"
  llm_context_length: 8192
```

The `swarm` block is separate from `llm` (provider config) because
users often change providers without changing swarm size.

---

## 6. User Prompt Format

```
═══════════════════════════════════════════════════
   SMF Swarm — Hardware & Swarm Profile Setup
═══════════════════════════════════════════════════

Detected hardware:
  • RAM: 31.2 GB total (22.1 GB available)
  • CPU: 8 cores
  • GPU: Not detected

Recommended profile: [4] Deep Analysis

Choose your swarm profile:

  [1] Essential           — 3 agents, 20 steps, ~6 GB, qwen2.5:3b
                           (Fast checks, minimal hardware)

  [2] Compact    *        — 5 agents, 50 steps, ~8 GB, qwen2.5:7b
                           (Default baseline — safe on most laptops)

  [3] Balanced   *        — 8 agents, 100 steps, ~12 GB, qwen2.5:7b
                           (Standard predictions — good compromise)

  [4] Deep Analysis  ←    — 12 agents, 200 steps, ~20 GB, qwen2.5:14b
                           (Recommended — uses detected hardware well)

  [5] Ensemble            — 20 agents, 400 steps, ~36 GB, qwen2.5:32b
                           (Unavailable — requires 32+ GB RAM)

  [6] Custom              — Define agent count, steps, and model

  <Enter> defaults to the recommended profile [4]

Your choice [1-6]: _
```

The prompt shows **unavailable profiles** but disabled, so the user
sees what their hardware is *preventing* them from using. This
subtly communicates that buying more RAM would unlock more predictive
depth — a natural upgrade incentive.

---

## 7. Implementation Modules

### Directory Structure

```
src/smf_swarm/
├── resource_profiler/
│   ├── __init__.py          # Public API: detect(), recommend(), prompt()
│   ├── detector.py          # Hardware detection
│   ├── registry.py            # Profile definitions + filtering
│   ├── prompter.py          # Terminal + TUI user choice
│   └── configurator.py      # Apply profile to SwarmConfig
```

### Module Responsibilities

|`detector.py`|Cross-platform hardware detection. Pure functions — no side effects.|
|`registry.py`|Immutable profile definitions. Filter logic. No I/O.|
|`prompter.py`|User interaction. Blocks until choice made. Returns chosen profile name.|
|`configurator.py`|Side-effect: reads/writes `~/.config/smf-swarm/config.yaml`. Applies chosen profile.|

### Integration Points

```python
# In cli.py → configure()
from smf_swarm.resource_profiler import run_profilers

def configure():
    # ... existing LLM config steps 1-4 ...

    # Step 5 (NEW): Resource profile selection
    profile = run_profilers()  # detects, recommends, prompts, persists

    # ... save and finish ...
```

Also callable standalone:
```bash
smf-swarm profile            # Run profile wizard
smf-swarm profile --auto     # Auto-detect and apply recommended (non-interactive)
smf-swarm profile --show     # Display current profile without changing
smf-swarm profile --reset    # Force re-detection on next run
```

---

## 8. Testing Strategy

| Test | Method |
|:-----|:-------|
| Detection accuracy | Run on machines with known RAM/GPU, assert within 10%. |
| OOM prevention | Load a RAM-limited Docker container (e.g., `--memory=6g`), verify recommended profile uses ≤ 75%. |
| User override | Mock user input choosing a smaller profile, verify saved config reflects choice. |
| Cross-platform | Run on Ubuntu, macOS, and Windows CI runners. |
| Graceful degradation | Remove `psutil`, verify falls back to conservative `essential` profile + warning. |

---

## 9. Open Questions

1. **Should we add a "turbo" override flag?** `--turbo` could push
the swarm to 90% of detected RAM. Useful for batch runs on headless
servers, dangerous for interactive sessions.

2. **Dynamic step reduction?** If during a run we detect memory
pressure (via `psutil.virtual_memory().percent`), should we
auto-reduce the next batch of agents? This is complex but would
prevent mid-run OOMs.

3. **Profile benchmarking?** Should we include a `smf-swarm benchmark`
command that runs a lightweight test swarm to empirically measure
actual memory usage, rather than relying on heuristics?

---

## 10. References

- Du et al. (2023) — *Improving Factuality of Language Models via
  Multi-Agent Debate* (arXiv:2305.14325)
- Zhao et al. (2026) — *ProMAS: Error Forecasting for Multi-Agent
  Systems* (arXiv:2603.20260)
- Kimi Agent Swarms announcement — "300 parallel sub-agents, 4,000
  steps per run" (2026-04)
- MiroFish-Offline hardware requirements doc (32 GB recommended)
