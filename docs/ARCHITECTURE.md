# SMF Swarm — System Architecture

**Language:** Python 3.10+  
**Total modules:** 12 (config, pipeline, debate, social, monitor, CLI)  
**Est. SLOC:** ~3,000 (productized), ~5,500 (including docs)

---

## 1. High-Level Concept

SMF Swarm is a **custom sequential hybrid predictive pipeline** that combines three
information channels into a single confidence-calibrated forecast via a deterministic
state machine:

1. **Standard** — Analytical model on engineered features
2. **Debate** — Adversarial ensemble (Optimist vs Skeptic vs Analyst)
3. **Social** — Agent swarm calibration on discourse and sentiment

The pipeline is intentionally sequential (not graph-based) to ensure deterministic
outputs, eliminate deadlocks, and simplify debugging. Parallelism is applied
selectively where nodes are independent.

**The social layer alone cannot make predictions.** It is explicitly
dependent on the standard debate layer's content for seeding, producing a
calibration signal rather than a raw forecast.

---

## 2. Prediction Modes

```
┌──────────────┬──────────────┬──────────────┬──────────────┐
│   Standard   │    Debate    │  Full+Social │ Social Swarm │
│              │              │              │ Standalone   │
├──────────────┼──────────────┼──────────────┼──────────────┤
│ Gather       │ Gather       │ Gather       │              │
│ Engineer     │ Engineer     │ Engineer     │              │
│ Reflect      │              │ Reflect      │              │
│ Model        │              │ Model        │              │
│ Validate     │              │ Validate     │              │
│              │ Debate       │ Debate       │              │
│              │              │ Merge        │              │
│              │              │ Social       │ Social       │
│ Report       │ Report       │ Report       │ Report (text)│
└──────────────┴──────────────┴──────────────┴──────────────┘
                              │              │
                              │ Dependency   │ Independent
                              │ Seed debate  │ No prediction
                              │ content      │ into swarm
```

## 3. Data Flow

```
User Query
    │
    ▼
┌─────────────────────────────────────────┐
│ [Node: Data Gatherer]                   │
│ LLM call: Sources, indicators, quality  │
│ Output: raw_data, data_quality_score    │
│ ~1 LLM invocation                       │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ [Node: Feature Engineer]                │
│ LLM call: Top N predictive features     │
│ Output: features, feature_count        │
│ ~1 LLM invocation                       │
└─────────────────────────────────────────┘
    │
    ├──(Standard/Full)──► Reflection ──► Model Runner
    │                                    │
    │              ┌──────────────────────┴──────────┐
    │              │ [Node: Model Runner]            │
    │              │ LLM call: Prediction + confidence │
    │              │ Output: prediction, confidence    │
    │              │ ~1 LLM invocation               │
    │              └─────────────────────────────────┘
    │                            │
    │              ┌─────────────┘
    │              ▼
    │   ┌─────────────────────────────────────────┐
    │   │ [Node: Validator]                       │
    │   │ LLM call: PASS/FAIL validation          │
    │   │ Output: validation_passed              │
    │   │ ~1 LLM invocation                     │
    │   └─────────────────────────────────────────┘
    │              │
    │              ▼ (if validation fails, refine + re-model)
    │
    ├──(Debate/Full)──► Debate Engine
    │                   │
    │          ┌────────┴────────────┐
    │          ▼                     ▼
    │   [Opt. Opening]         [Skep. Opening]
    │   1 call                    1 call
    │          │                     │
    │          ▼                     ▼
    │   [Analyst Opening]      [Analyst Rebuttal]
    │   1 call                      1 call
    │          │                     │
    │          ▼                     ▼
    │   [Opt. Rebuttal]        [Skep. Rebuttal]
    │   1 call                      1 call
    │          │                     │
    │          ▼                     ▼
    │        [Judge]             [Dissent]
    │        1 call                 1 call
    │          │
    │   Output: debate_consensus, debate_confidence
    │   Total: 8 LLM calls
    │
    └──(Full)──► Merge Node
               │
               ▼
        ┌──────────────────────────────────────┐
        │ Merge Standard + Debate              │
        │  LLM call with both predictions      │
        │  Output: final_consensus             │
        │  ~1 LLM invocation                   │
        └──────────────────────────────────────┘
               │
               ▼
        Social Simulation Swarm
               │
          ┌────┴──────────────────────────────┐
          ▼                                   ▼
    [Generate Personas]
    Templates per domain:
    - technology: VCs, researchers, founders
    - financial: CFOs, PMs, regulators
    - political: pollsters, strategists, activists
           │
           ▼
    [Run Simulation]
    Per round:
    - Each active persona generates an action via LLM (~5 agents active/round)
    - Sentiment extracted from each action
    Total: 5–15 LLM calls (depends on agent_count × activity rate)
           │
           ▼
    Output: confidence_modifier, sentiment_trajectory, social_report
           │
           ▼
    Applied to final_considence: conf_adj = conf + modifier × 0.2
           │
           ▼
    Final Report Generation (summarize everything)

Total LLM invocations per mode:
  Standard: ~5
  Debate:   ~11 (Gather + Engineer + 8 debate + Report)
  Full:     ~22 (Standard (~5) + Debate (~8) + Merge (1) + Social (~5–15) + Report (1))
```

## 4. Module Breakdown

```
smf_swarm/
├── __init__.py          # Package entry, exports Pipeline, config, version
├── config.py            # Config dataclass, wizard, env overrides, LLM factory
├── pipeline.py          # Public API: Pipeline.run(), result object, node graph
├── cli.py               # Terminal entry point: smf-swarm command
├── debate/
│   └── engine.py        # 3-agent debate: openings, rebuttals, judge, dissent
│                          DebateEngine class, prompt templates, confidence extraction
├── social/
│   └── simulator.py     # Social swarm simulation: personas, actions, sentiment,
│                        knowledge graph, report generation
└── monitor/
    └── __init__.py      # SwarmMonitor: node timing, error tracking, health_score
```

## 5. Config System

**File:** `~/.config/smf-swarm/config.yaml`  \
**Created by:** `smf-swarm configure` wizard  \
**Overridden by:** Environment variables `MODEL_NAME`, `OPENAI_BASE_URL`, `O_API_KEY`

```yaml
llm:
  provider: ollama          # ollama | openai | anthropic | custom
  model: kimi-k2.6:cloud
  base_url: http://localhost:11434/v1
  api_key: ollama
  temperature: 0.3
  timeout: 180
  max_retries: 1
default_mode: debate
default_domain: general
social_agents: 15
social_rounds: 4
debaters: 3
debate_rounds: 2
output_dir: "/home/user/smf-swarm/output"
memory_dir: "/home/user/smf-swarm/memory"
verbose: true
```

## 6. Result Object

```python
class PipelineResult:
    query: str
    domain: str
    mode: str
    confidence: float
    prediction_text: str
    summary: str
    risk: str
    data_quality: float
    duration_s: float
    social_modifier: Optional[float]
    health_score: float
    timestamp: str
    status: str  # COMPLETED | FAILED | PENDING
```

## 7. Health Monitoring

Every node execution is timed and tracked:
- **duration_s**: wall-clock time per node
- **success**: boolean pass/fail
- **error**: traceback string if failed
- **health_score**: `1.0 − (errors / total_nodes)`

Per-run health report example:
```json
{
  "pipeline_status": "completed",
  "pipeline_duration_s": 482.0,
  "node_count": 14,
  "errors": 0,
  "health_score": 1.0
}
```

## 8. Extending the Pipeline

### Adding a New Node

1. Define the node function in `pipeline.py`
2. Insert it in `Pipeline._run_state_machine()` after the target predecessor
3. Wrap with `self.monitor.track("node_name")` for health tracking

```python
def _custom_node(self, state: dict) -> dict:
    with self.monitor.track("custom_node"):
        resp = self.llm.invoke([HumanMessage(content=f"Custom prompt: {state['query']}")])
        return {"custom_result": resp.content}
```

### Adding a New Domain

1. Add persona templates to `SocialSimulator._get_templates()` in `social/simulator.py`
2. Add domain name to config validation in `config.py`

### Adding a New LLM Provider

If the provider has an OpenAI-compatible API (most do), just set:
- `provider: custom` (or `openai`)
- `base_url: https://your-provider.com/v1`
- `model: provider-model-name`

If not, create an adapter in `llm_adapters.py` following the LangChain interface.

## 9. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Sequential node execution | Eliminates deadlocks, simpler debugging, deterministic LLM outputs. Parallelism applied selectively for independent nodes (e.g., debate openings). |
| `last-match` confidence extraction | Prevents intermediate "confidence" mentions from corrupting extracted score |
| Reflection node before model runner | Forces explicit CoT extraction before prediction, reducing hidden-assumption errors |
| Confidence modifier × 0.2 scaling | Prevents social layer from dominating prediction; acts as calibration, not oracle |
| Immutability (config file) + env override | Persistent config for daily use, env variables for CI/testing |

## 10. Performance Characteristics

| Mode | LLM Calls | Avg Duration (local GPU) | Avg Duration (Ollama cloud) |
|------|-----------|--------------------------|----------------------------|
| Standard | 5 | ~2 min | ~7 min |
| Debate | 11 | ~5 min | ~16 min |
| Full | 20 | ~15 min | ~45–80 min |

*(Cloud model: Kimi K2.6 via Ollama; Local GPU: RTX 4090 with 7B model)*

---

*Architecture by Liam Hermes, Chief Data Officer, SMF Works*
