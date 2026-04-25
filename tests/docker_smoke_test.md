# Docker Smoke Test — Runbook for SMF Swarm v1.4.1

## Quick Test (~2 minutes)
```bash
cd /home/mikesai2/smf-works/smf-swarm
docker build -t smf-swarm:1.4.1 .
docker run --rm smf-swarm:1.4.1 version
```
Expected output: `1.4.1`

## Full Web UI Test (~3 minutes)
```bash
docker run -p 8080:8080 --rm smf-swarm:1.4.1 web --host 0.0.0.0 --port 8080
```
Then in another terminal:
```bash
curl http://localhost:8080/health
```
Expected: JSON with `"status": "ok"`.

## What to Watch For
1. **Build time** — First build downloads base image and installs deps (~2-3 min). Subsequent builds use layer cache.
2. **Import warnings** — `torch.cuda` warnings about old drivers are expected on this machine. They do not affect functionality.
3. **`duckduckgo_search` rename warning** — Expected; package deprecated its old name.
4. **ModuleNotFoundError for `langgraph`** — The base `Dockerfile` uses `pip install -e .` without extras. The LangGraph backend will fallback to classic pipeline. This is fine for a smoke test. To test LangGraph in Docker, change the install line to `pip install -e ".[langgraph,predict,trust]"`.

## Known Good Exit Codes
- `0` on `version` command → OK
- `0` on `web` startup → OK (process keeps running)
- `1` on build → Check `pyproject.toml` syntax or network issues
