# SMF Swarm — Full CLI Reference

## `smf-swarm`

Main entry point. All commands are subcommands.

### `smf-swarm configure`

Run the first-time interactive configuration wizard.

```bash
smf-swarm configure
```

Creates `~/.config/smf-swarm/config.yaml` with your LLM settings.

---

### `smf-swarm predict <query>`

Run a prediction query.

```bash
# Basic usage (uses default mode and domain)
smf-swarm predict "Will X happen?"

# Specify mode
smf-swarm predict "Will X happen?" --mode full

# Specify domain
smf-swarm predict "Will X happen?" --domain technology

# Disable social simulation (even in full mode)
smf-swarm predict "Will X happen?" --mode full --no-social

# Save to JSON
smf-swarm predict "Will X happen?" -o result.json
```

| Flag | Options | Default |
|------|---------|---------|
| `--mode` | `standard`, `debate`, `full` | From config (wizard defaults to `debate`) |
| `--domain` | `technology`, `financial`, `political`, `general` | From config (`general`) |
| `--no-social` | (flag) | Social enabled by default in `full` mode |
| `-o`, `--output` | File path | Print to terminal only |

---

### `smf-swarm test`

Verify your LLM connection is working.

```bash
smf-swarm test
```

Sends a simple "what is 2+2?" test call and reports whether the
connection succeeded or failed.

If connection fails, it prints troubleshooting steps:
- Is Ollama running? (`ollama serve`)
- Is the base URL correct?
- Did the model download complete?

---

### `smf-swarm version`

Show version, author, and contact.

```bash
smf-swarm version
```

---

### `smf-swarm config`

Display the current configuration in effect.

```bash
smf-swarm config
```

Shows the path to your config file and all current settings.

---

## Examples

### Real-time dashboard signal

```bash
#!/bin/bash
RESULT=$(smf-swarm predict "Will NVIDIA close above $150 today?" --mode standard --domain financial)
echo "$RESULT" | grep "Confidence"
```

### Weekly strategic report

```bash
smf-swarm predict "Will the Fed cut rates in June?" \
  --mode debate \
  --domain financial \
  -o weekly_report.json
```

### Batch of queries

```bash
for q in "Will inflation stay above 3%?" "Will Bitcoin exceed 100K?"; do
  smf-swarm predict "$q" --mode standard -o "$(echo $q | tr ' ' '_').json"
done
```

---

## Python API

```python
from smf_swarm import Pipeline

p = Pipeline()
result = p.run("Will X happen?", mode="full", domain="technology")

# Access structured data
print(result.confidence)
print(result.summary)
print(result.risk)
print(result.duration_s)

# Custom LLM
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(model="gpt-4o", temperature=0.3, timeout=180)
p = Pipeline(llm=llm)
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full data model and node graph.

---

*Documentation by SMF Works. Email michael@smfworks.com for questions.*
