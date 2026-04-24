# SMF Swarm 🎯

**Custom Sequential Hybrid Pipeline with Adversarial Debate and Social Calibration**

Predict the future with agent swarms. SMF Swarm runs three prediction modes
— Standard, Debate, and Full+Social — powered by any LLM you choose
(local or cloud).

Built by [SMF Works](https://smfworks.com). MIT licensed. Open source.

**👤 Who is this for?** SMF Swarm is a developer/engineer tool. You interact with it via the command line or Python API. If you want a conversational, no-code experience, see [SMF Predict](https://smfworks.com/predict) — a commercial product that bundles SMF Swarm with a pre-configured Hermes Agent (or any OpenClaw-compatible agent) so you can type natural-language questions and get polished forecast reports back.

**⚙️ Hardware-Aware Scaling.** On first run, SMF Swarm detects your available RAM and GPU VRAM, then recommends an agent-swarm profile sized for your machine — ranging from **Compact** (4 agents, runs comfortably on systems with as little as **8 GB RAM**) up to **Enthusiast** (12+ agents, for workstations with 32 GB+ RAM or discrete GPUs). You always retain full control: override the recommendation, choose a custom size, or lock your profile for future runs.

**🌐 Web UI.** Prefer a point-and-click experience? SMF Swarm ships with a standalone web interface at `http://localhost:8080` — zero configuration, entry-level friendly, and perfect for users who want predictions without touching the terminal.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Standard Mode** | Fast single-model prediction. Gather data, engineer features, model, validate, report. |
| **Debate Mode** | Adversarial ensemble — Optimist vs Skeptic vs Analyst, with opening arguments and rebuttals. |
| **Full + Social** | Standard + Debate → merge → social swarm validation (agent swarm calibration). |
| **Web UI** | Standalone web interface for entry-level, no-code use. Point-and-click predictions in your browser. Optional bearer-token auth and rate limiting. |
| **Hardware-Aware Scaling** | Auto-detects RAM / VRAM on first run and recommends a swarm profile sized for your machine — works on 8 GB workstations. Override or lock at any time. |
| **LangGraph Execution** *(v1.4.0+)* | Optional `[langgraph]` extra. Production `StateGraph` backend: node-level checkpointing, retry policies, `MemorySaver` persistence, parallel multi-sample Map-Reduce. Soft-switch auto-detects via `LANGGRAPH_AUTO=1`. |
| **Any LLM Provider** | Ollama, OpenAI, Anthropic, Groq, Together, or any OpenAI-compat API. Swap models in one command. |
| **Health Monitoring** | Per-node tracking: duration, errors, success rate, and dynamic ETA estimates. |
| **Structured Output** | Pydantic-validated JSON extraction for confidence, validation, features, and sentiment. Hardened regex fallback for non-compliant models. |
| **Response Caching** | Disk-based LLM query cache with SHA-256 keyed by query+config+mode. TTL default 24 h. Repeat experiments bypass all LLM calls. `--no-cache` to force fresh runs. |
| **Parallel Debate** | Optimist and Skeptic openings run concurrently via `ThreadPoolExecutor` for ~30–40 % debate speedup. |
| **Docker Ready** | `Dockerfile` + `docker-compose.yml` for one-command deployment with Ollama sidecar. |
| **Secure Config** | Optional OS keyring integration for API keys. Config file is `chmod 0o600` on every save. |

---

## 🚀 One-Line Install (macOS / Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/smfworks/smf-swarm/main/install.sh | bash
```

After install, run the configuration wizard:

```bash
smf-swarm configure
```

---

## 📚 Table of Contents

- [Quick Start](#-quick-start)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Documentation](#-documentation)
- [API Reference](#-api-reference)
- [Support & Contact](#-support--contact)
- [License](#-license)

---

## ⚡ Quick Start

### 1. Prerequisites
- Python 3.10+
- An LLM backend (one of the following):
  - [Ollama](https://ollama.com/) (recommended for beginners — runs entirely locally)
  - OpenAI API key
  - Anthropic API key
  - Any OpenAI-compatible endpoint

### 2. Install

```bash
pip install smf-swarm
```

Or install from source:

```bash
git clone https://github.com/smfworks/smf-swarm.git
cd smf-swarm
pip install -e .
```

### 3. Configure

Run the interactive wizard:

```bash
smf-swarm configure
```

It will ask you for:
1. LLM provider (Ollama / OpenAI / Anthropic / Custom)
2. Model name
3. API base URL
4. API key
5. Default prediction mode

### 4. Test

```bash
smf-swarm test
```

You should see:

```
✅ Connection OK — model: llama3.3
   Response: 4
```

### 5. Predict

```bash
smf-swarm predict "Will NVIDIA market cap exceed $4 trillion by July 2026?" \
  --mode full --domain financial
```

**LangGraph execution** *(v1.4.0+)* — enable the `StateGraph` backend for checkpointing, retries, and parallel multi-sample:

```bash
# Install the extra
pip install smf-swarm[langgraph]

# Auto-detect (uses LangGraph when available)
export LANGGRAPH_AUTO=1
smf-swarm predict "..." --mode full

# Force LangGraph for this run
smf-swarm predict "..." --mode full --langgraph

# Force classic synchronous path
LANGGRAPH_DISABLE=1 smf-swarm predict "..." --mode full
```

Output:

```
╔════════════════════════════════════════════════════════════╗
  RESULT
╚════════════════════════════════════════════════════════════╝
  Confidence:      0.78
  Data Quality:    0.42
  Health Score:    0.95
  Duration:        482s
  Social Modifier: -0.15

  EXECUTIVE SUMMARY
  ──────────────────────────────────────────────────────────
  NVIDIA's trajectory toward a $4 trillion valuation by
  mid-2026 remains plausible but hinges on sustained AI...
```

---

## 🌐 Web UI (v1.1.0+)

Launch a slick browser-based interface for casual users — no terminal required.

```bash
smf-swarm web
```

**Output:**
```
🎯  SMF Swarm Web UI
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Server:   http://127.0.0.1:8080
Press Ctrl+C to stop
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Features:**
- Dark glassmorphism design (zero external CSS frameworks)
- Mode selector: Standard | Debate | Full+Social
- Domain selector: Technology | Financial | Political | General
- Report upload: drag-and-drop PDF, TXT, or Markdown for pipeline context
- Real-time SSE streaming: watch each pipeline node execute live
- **LangGraph streaming** *(v1.4.0+)*: POST to `/api/predict/langgraph` for native checkpointed execution with identical SSE surface
- Confidence arc visualization with amber/gold colorway
- Dissent and social simulation sections when applicable
- **Download Report**: one-click Markdown export of any finished forecast

**Custom port:**
```bash
smf-swarm web --port 3000 --host 0.0.0.0
```

**⚠️ Security note:** Binding to `0.0.0.0` exposes the Web UI on your network. Use `--token <secret>` (or `WEB_TOKEN` env var) to enable bearer-token authentication. Rate limiting is active by default.

The Web UI is self-contained — Flask API + vanilla JS + HTML5. No external CDN assets. Works offline after install.

---

## 📖 Documentation

| Document | Audience | What You'll Learn |
|----------|----------|-----------------|
| [`docs/SETUP.md`](docs/SETUP.md) | First-time users | Step-by-step install & config, including Ollama setup |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Developers | System design, node graph, data flow, extension guide |
| [`docs/USAGE.md`](docs/USAGE.md) | All users | Complete CLI reference and Python API |
| [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) | Contributors | Code style, PR process, issue templates |
| [`docs/CHANGELOG.md`](docs/CHANGELOG.md) | Users | Version history and migration notes |

---

## 🔧 Python API

```python
from smf_swarm import Pipeline

p = Pipeline()
result = p.run(
    "Will AI agent adoption in enterprise exceed 60% by end 2026?",
    mode="full",
    domain="technology",
    langgraph=True,  # v1.4.0+ — use LangGraph backend (checkpointing, retries)
)

print(result.confidence)       # 0.82
print(result.summary)          # Executive summary text
print(result.duration_s)       # 4936.0
```

Customize LLM at init time:

```python
from smf_swarm import Pipeline, load_config
from langchain_openai import ChatOpenAI

cfg = load_config()
my_llm = ChatOpenAI(model="gpt-4o", base_url="https://api.openai.com/v1", api_key="sk-...")
p = Pipeline(llm=my_llm)
result = p.run("Will inflation in the US exceed 3% by Q4 2025?")
```

---

## 👤 User Guide

### Choosing a Mode

| Mode | Speed | Depth | Best For |
|------|-------|-------|----------|
| `standard` | Fast (~6–8 min) | Single-model | Quick signals, high-frequency monitoring |
| `debate` | Medium (~15–18 min) | Adversarial ensemble | Medium-stakes decisions |
| `full` | Slow (~40–80 min) | Everything + swarm validation | High-stakes, public forecasts |

### Choosing a Domain

Domains tune persona templates in the social simulation layer:
- `technology` — tech analysts, VCs, researchers, regulators
- `financial` — CFOs, portfolio managers, risk analysts, regulators
- `political` — pollsters, strategists, activists, political scientists
- `general` — domain-agnostic analysts

### Environment Variables

Override config without re-running the wizard:

| Variable | Purpose |
|----------|---------|
| `MODEL_NAME` | e.g., `kimi-k2.6:cloud`, `gpt-4o`, `llama3.3` |
| `OPENAI_BASE_URL` | e.g., `http://localhost:11434/v1` |
| `O_API_KEY` | API key (any string for Ollama, real key for cloud) |

---

## 🧪 Testing

```bash
pytest tests/
```

Smoke test (no pytest required):

```bash
smf-swarm test
```

---

## 🐛 Troubleshooting

| Problem | Fix |
|---------|-----|
| `Connection refused` | Is Ollama running? Run `ollama serve` in another terminal. |
| Model not found | Run `ollama pull llama3.3` (or your model) before using it. |
| Empty predictions | Increase timeout: set `timeout: 300` in `~/.config/smf-swarm/config.yaml`. |
| Import error | Upgrade: `pip install -U smf-swarm` |

---

## 📬 Support & Contact

| Channel | Handle |
|---------|--------|
| Email | michael@smfworks.com |
| X / Twitter | [@michaelgannotti](https://x.com/michaelgannotti) |
| GitHub Issues | [smfworks/smf-swarm/issues](https://github.com/smfworks/smf-swarm/issues) |

---

## 🤖 Agent Integration

Want to use SMF Swarm from a conversational agent? You can hook it into an existing **Hermes Agent** or **OpenClaw Agent** in two ways:

### Option 1: In-process import (fastest)
Your agent runs in Python and calls the Swarm directly:

```python
from smf_swarm import Pipeline

pipeline = Pipeline()
result = pipeline.run(
    query="Will NVIDIA exceed $4T by July 2026?",
    mode="debate",
    domain="financial"
)
# Feed result.confidence, result.summary back to your agent
```

### Option 2: Subprocess call (isolated)
Shell out from any language:

```bash
smf-swarm predict "Will AI adoption exceed 60%?" --mode full --domain technology --output result.json
```

Your agent reads `result.json` and presents it to the user.

For a turnkey, pre-integrated solution with license management and automated research, see [SMF Predict](https://smfworks.com/predict).

---

## 🏗️ Project Information

- **Organization:** SMF Works
- **License:** MIT (see [`LICENSE`](LICENSE))
- **Python:** 3.10, 3.11, 3.12
- **Package:** `smf-swarm` on PyPI

---

## ⭐ Star History

If you find SMF Swarm useful, please star the repo and share your use cases. We read every issue and feature request.

---

*Built by Liam Hermes, Chief Data Officer, SMF Works.*  
*Predicting the future, one swarm at a time.*
