# SMF Swarm — Step-by-Step Setup Guide

**If you've never installed a Python package or run a terminal command before,
this guide is for you.**

Estimated time: **10–15 minutes**.

---

## Step 1: Check Prerequisites

### Python 3.10 or higher

Open your terminal and type:

```bash
python3 --version
```

If it prints `3.10.x`, `3.11.x`, or `3.12.x`, you're good.

If it says "command not found" or shows `3.9.x`, install Python:
- **macOS**: `brew install python`
- **Ubuntu/Debian**: `sudo apt update && sudo apt install python3 python3-pip`
- **Fedora**: `sudo dnf install python3 python3-pip`
- **Windows**: Download from [python.org](https://python.org/downloads/)

---

## Step 2: Install SMF Swarm

### Option A: One-line install

**macOS / Linux (bash):**

```bash
curl -fsSL https://raw.githubusercontent.com/smfworks/smf-swarm/main/install.sh | bash
```

**Windows (PowerShell):**

```powershell
iwr -useb https://raw.githubusercontent.com/smfworks/smf-swarm/main/install.ps1 | iex
```

> Use Windows Terminal or PowerShell 7+ for the best CLI experience. Legacy `cmd.exe` users: download `install.bat` instead.

This downloads and installs `smf-swarm` and its dependencies automatically.

### Option B: pip install (any OS)

```bash
pip install smf-swarm
```

If `pip` is not found, try `pip3` instead.

### Option C: Install from source

```bash
git clone https://github.com/smfworks/smf-swarm.git
cd smf-swarm
pip install -e .
```

---

## Step 3: Get an LLM (Choose One Path)

SMF Swarm needs a "brain" to run predictions. You can use a **local** model
(your computer runs it) or a **cloud** model (someone else's computer runs it).

### Path A: Local with Ollama (Recommended Beginners)

Ollama lets you run AI models on your own machine for free.
No API keys, no monthly bills.

**A1. Install Ollama**

- **macOS**: Visit [ollama.com/download](https://ollama.com/download) and install the app
- **Linux**: Run `curl -fsSL https://ollama.com/install.sh | sh`

**A2. Start Ollama**

Keep this terminal open:

```bash
ollama serve
```

You should see: `Ollama is running`.

**A3. Download a model**

In a *new* terminal tab (keep the first one open):

```bash
ollama pull llama3.3
```

This downloads a ~20 GB file. Go get coffee. ☕

**A4. Test it works**

```bash
ollama run llama3.3 "What is 2+2?"
```

Should print: `4`.

---

### Path B: OpenAI (Cloud)

**B1. Get an API key**

1. Go to [platform.openai.com](https://platform.openai.com)
2. Sign up / log in
3. Click your profile → "View API keys"
4. Click "Create new secret key"
5. Copy the key (it starts with `sk-...`)

**B2. You'll enter this key during the configuration wizard in Step 4.**

---

### Path C: Anthropic / Other (Cloud)

1. Get an API key from your provider
2. Note the **base URL** (for Anthropic: `https://api.anthropic.com/v1`)
3. Note the **model name** (for Claude: `claude-3-opus-20240229`)

You'll enter both during the configuration wizard.

---

## Step 4: Run the Configuration Wizard

```bash
smf-swarm configure
```

The wizard will ask you 5 questions. Here's what to type for each path:

### If you chose Ollama (Path A)

| Question | Answer |
|----------|--------|
| Provider | `1` (Ollama) |
| Model name | `llama3.3` (or whatever you downloaded) |
| Base URL | Press Enter to accept default (`http://localhost:11434/v1`) |
| API key | Press Enter to accept default (`ollama`) |
| Default mode | `2` (Debate — best balance) |

### If you chose OpenAI (Path B)

| Question | Answer |
|----------|--------|
| Provider | `2` (OpenAI) |
| Model name | `gpt-4o` |
| Base URL | Press Enter for `https://api.openai.com/v1` |
| API key | Paste your key here (no one can see it) |
| Default mode | `2` (Debate) |

### If you chose Custom (Path C)

| Question | Answer |
|----------|--------|
| Provider | `4` (Custom) |
| Model name | Paste your model name |
| Base URL | Paste your provider's base URL |
| API key | Paste your key |
| Default mode | `2` (Debate) or `3` (Full) |

**What the wizard actually does:** It creates a platform-appropriate config file —
`~/.config/smf-swarm/config.yaml` on macOS/Linux or `%APPDATA%\SMF-Swarm\config.yaml` on Windows —
with your settings. You can edit this file later with any text editor.

---

## Step 5: Verify Everything Works

```bash
smf-swarm test
```

Expected output:

```
Testing connection...
✅ Connection OK — model: llama3.3
   Response: 4
```

If you see an error, see [Troubleshooting](#troubleshooting) below.

---

## Step 6: Run Your First Prediction

```bash
smf-swarm predict "Will NVIDIA market cap exceed $4 trillion by July 2026?" \
  --mode full --domain financial
```

You will see output like:

```
MODE: FULL + SOCIAL
Confidence: 0.78
Duration: 482s
Social Modifier: -0.15

EXECUTIVE SUMMARY:
NVIDIA's trajectory toward a $4 trillion valuation...
```

🎉 **You are predicting. Welcome to SMF Swarm.**

---

## Step 7: Explore

- Try different modes: `--mode standard`, `--mode debate`, `--mode full`
- Try different domains: `--domain technology`, `--domain political`
- Run headless and save JSON: `--output result.json`

---

## Troubleshooting

### "Connection refused" error
- Is Ollama running? Re-run `ollama serve` in another terminal.
- Is the base URL correct? If Ollama is on another machine, use its IP.

### "Model not found" error
- Run `ollama pull llama3.3` (or your chosen model) before using it.

### "Empty predictions" or timeouts
- Increase timeout in config (macOS/Linux: `nano ~/.config/smf-swarm/config.yaml`, Windows: open `%APPDATA%\SMF-Swarm\config.yaml`):
- Change `timeout: 180` to `timeout: 300`.

### "Permission denied" when running install
- Make sure Python is in your PATH.
- Try: `pip install --user smf-swarm`

### Still stuck?
- Email: michael@smfworks.com
- X: [@michaelgannotti](https://x.com/michaelgannotti)
- GitHub Issues: [smfworks/smf-swarm/issues](https://github.com/smfworks/smf-swarm/issues)

---

## Next Steps

- Read the full [Architecture Guide](ARCHITECTURE.md) to understand how it works
- Learn about [Contributing](CONTRIBUTING.md) if you want to help build it
- Check the [Usage Guide](USAGE.md) for advanced CLI features

---

*Written for new users by SMF Works. Predicting the future should be accessible to everyone.*
