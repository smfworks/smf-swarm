# SMF Swarm 🎯

**LangGraph + CrewAI + MiroFish Hybrid Predictive Pipeline**

Predict the future with agent swarms. SMF Swarm runs three prediction modes
— Standard, Debate, and Full+Social — powered by any LLM you choose
(local or cloud).

Built by [SMF Works](https://smfworks.com). MIT licensed. Open source.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Standard Mode** | Fast single-model prediction. Gather data, engineer features, model, validate, report. |
| **Debate Mode** | Adversarial ensemble — Optimist vs Skeptic vs Analyst, with opening arguments and rebuttals. |
| **Full + Social** | Standard + Debate → merge → MiroFish social validation (agent swarm calibration). |
| **Any LLM Provider** | Ollama, OpenAI, Anthropic, Groq, Together, or any OpenAI-compat API. Swap models in one command. |
| **Health Monitoring** | Per-node tracking: duration, errors, success rate. |
| **Structured Output** | JSON output with confidence, summary, risk assessment, and timestamps. |

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
    domain="technology"
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
