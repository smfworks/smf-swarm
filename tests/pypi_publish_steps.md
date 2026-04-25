# PyPI Publication Checklist — SMF Swarm v1.4.1

## Prerequisites
- PyPI account: `smfworks` (create at https://pypi.org/account/register/)
- API token generated at https://pypi.org/manage/account/token/
- Token stored as `TWINE_PASSWORD` env var or in `~/.pypirc`:
  ```ini
  [pypi]
  username = __token__
  password = pypi-AgEIcH... (your token)
  ```

## Step-by-Step
```bash
cd /home/mikesai2/smf-works/smf-swarm

# 1. Ensure version is bumped (already done for 1.4.1)
.venv/bin/python -c "import smf_swarm; print(smf_swarm.__version__)"
# Expected: 1.4.1

# 2. Clean old dist/ builds
rm -rf dist/ build/ *.egg-info

# 3. Build distributable artifacts
.venv/bin/python -m pip install build twine
.venv/bin/python -m build
# Output: dist/smf_swarm-1.4.1.tar.gz + dist/smf_swarm-1.4.1-py3-none-any.whl

# 4. Upload to PyPI
twine upload dist/*
# Enter username (__token__) and password (your API token) if not in .pypirc

# 5. Verify
pip install smf-swarm==1.4.1
python -c "import smf_swarm; print(smf_swarm.__version__)"
```

## Extras Strategy
The `pyproject.toml` defines three optional extra groups:
- **base** (default): core pipeline, web UI, caching
- `[predict]`: Prophet, statsmodels, scikit-learn for statistical baselines
- `[langgraph]`: LangGraph backend for StateGraph execution
- `[trust]`: keyring for secure API key storage

Recommend publishing with all extras documented but not auto-installed:
```bash
pip install "smf-swarm[langgraph,predict,trust]"
```

## Post-Publish
- Tag release on GitHub with release notes
- Update smfworks.com download links if applicable
- Tweet / post about v1.4.1 if part of launch cadence
