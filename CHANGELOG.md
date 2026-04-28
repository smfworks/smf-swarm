# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.7.0] — 2026-04-28

### Fixed — MAPIE v1.3 Compatibility
- **`src/smf_swarm/conformal.py`** — runtime fixes for MAPIE ≥1.3 API changes:
  - Updated imports to try `SplitConformalClassifier` / `SplitConformalRegressor` first, then fall back to legacy `MapieClassifier` / `MapieRegressor`.
  - `fit_mapie()` now detects `SplitConformalClassifier` and uses `prefit=True` + `conformalize()` instead of the legacy `.fit()` method.
  - `predict_mapie()` now calls `predict_set()` and handles the new `(y_pred, y_ps)` return shape with 3D→2D squeeze for class probabilities.
  - Changed q_hat None guard from fallback to `1.0` → fallback to `alpha` in margin calculation.
  - Added `bool(included)` coercion to prevent numpy array truthiness errors in set comprehension.
- **`tests/test_conformal.py`** — added `1e-9` tolerance to `test_predict_interval_yes` to account for floating-point rounding differences.

### Added — Combined v1.6.0 reconciled on HEAD

#### Conformal Prediction (`src/smf_swarm/conformal.py`)
- `ConformalPredictor` class implementing split conformal prediction (Angelopoulos & Bates, 2023).
- `ConformalInterval` dataclass: `low`, `high`, `margin`, `coverage_target`, `prediction_set`, `label`.
- `coverage_score()` — empirical test-set marginal coverage validation.
- `adaptive_binning()` — per-bin local `q̂` with underpopulation fallback (minimum 5 samples per bin).
- Optional MAPIE wrapper (`fit_mapie()`, `predict_mapie()`) via `[conformal]` extras.

#### FastAPI Server Mode (`src/smf_swarm/server/`)
- Full router set with Pydantic models, Bearer auth, rate limiting:
  - `POST /api/v1/predict` — async prediction queue (returns `job_id`)
  - `POST /api/v1/batch` — parallel batch (up to 100 items)
  - `POST /api/v1/benchmark` — queue benchmark runs
  - `POST /api/v1/calibrate` — conformal calibration endpoint
  - `GET /api/v1/jobs/{job_id}` — status & results
  - `GET /api/v1/jobs` — list active jobs
  - `DELETE /api/v1/jobs/{job_id}` — cancel queued/running job
  - `GET /api/v1/health` — liveness probe (public)
  - `GET /api/v1/config` — safe config subset
- SSE streaming endpoint `GET /api/v1/predict/stream/{job_id}`.
- `ServerJobRunner` wrapping existing `JobRunner` with batch / list / cancel.
- CLI subcommand: `smf-swarm server --host 0.0.0.0 --port 8080 --workers 4 --token <secret>`.
- New optional extras: `[api]` (`fastapi>=0.110.0`, `uvicorn>=0.27.0`).
- Tests: `tests/test_server.py` — 21 structural tests (health, config, predict, batch, calibrate, benchmark, jobs, rate limiting).

### Changed
- `pyproject.toml`: version bump `1.5.0` → `1.6.0`; added `[conformal]` extras (`mapie>=0.8.0`) and `[api]` extras (`fastapi>=0.110.0`, `uvicorn>=0.27.0`).
- `docs/ARCHITECTURE.md`: updated module tree to include `conformal.py` and `server/`.

---

## [1.5.0] — 2026-04-25

### Added
- **Benchmark Harness** (`smf-swarm benchmark` CLI)
  - `src/smf_swarm/benchmarks/harness.py`: `BenchmarkHarness` with `BenchmarkReport` — end-to-end dataset evaluation.
  - Brier score, ECE, MCE, accuracy, precision, recall, F1 per mode.
  - Naïve baselines: Always 50%, historical base rate, LogReg TF-IDF.
  - Reliability diagrams via matplotlib.
  - JSON + Markdown report export.
  - Results persisted to `BacktestStore`.
- **Dataset Fetcher** (`scripts/fetch_benchmark_data.py`)
  - Metaculus API v2 with optional `METACULUS_API_TOKEN`.
  - FiveThirtyEight MLB Elo CSV with multi-URL fallback.
  - `--dummy` flag for synthetic data generation.
  - Canonical JSONL schema.
- **Hardware Environment Logger** (`scripts/log_hw_env.py`)
  - CPU, RAM, GPU, OS, Python version, package manifest.
  - JSON export for reproducible runs.
- **New optional dependency group**: `[benchmark]` (`matplotlib>=3.8.0`, `scikit-learn>=1.3.0`, `requests>=2.31.0`).
- **New tests:**
  - `tests/test_benchmark_harness.py` — 14 tests.
  - `tests/test_benchmark_integration.py` — 4 tests.

### Changed
- `pyproject.toml`: version bumped to `1.5.0`; added `[benchmark]` extras.
- `src/smf_swarm/__init__.py`: version bump to `1.5.0`.
- `docs/ARCHITECTURE.md`: updated module tree.

---

## [1.4.1] — 2026-04-24

### Fixed
- **LangGraph `StateGraph.compile()` compatibility** (`src/smf_swarm/pipeline_langgraph.py`)
  - Removed deprecated `retry=` kwarg from `compile()`.
  - Fixes `TypeError: compile() got unexpected keyword argument 'retry'`.
- **Test suite green** — 4 auto-generated bugs fixed:
  - Missing `import pytest` patched.
  - `graph.draw_mermaid()` → `graph.get_graph().draw_mermaid()`.
  - MagicMock `_debate` attribute neutralized.
  - Unknown-node timing test corrected.

---

## [1.4.0] — 2026-04-24

### Added
- **LangGraph Execution Backend** (optional `[langgraph]` extra)
  - `src/smf_swarm/pipeline_langgraph.py`: production `StateGraph` adapter.
  - `compile_graph()` builds a 3-node graph: `gather → analyze → debate`.
  - `LangGraphJobRunner.run(...)` with `threading.Thread` + `Event` cancellation.
  - Auto-falls back to sequential pipeline when `langgraph` is not installed.
- **New tests:**
  - `tests/test_langgraph.py` — graph structure, edge definitions, conditional routing, event cancellation.
  - `tests/test_e2e_langgraph.py` — end-to-end run parity (`mock_llm=True`).
- `docs/LANGGRAPH.md` — technical deep-dive.

---

## [1.3.0] — 2026-04-20

### Added
- **Web UI** (`src/smf_swarm/web/`)
  - Standalone Streamlit browser app: dark/premium theme, live prediction dashboard.
  - Real-time swarm consensus display with confidence scoring.
  - Debate history viewer, result export (CSV/JSON).
  - Settings panel with model presets, temperature slider.
  - PWA support.

---

## [1.2.0] — 2026-04-17

### Added
- **Predictive credibility scoring**
  - Brier score, calibration error, multi-sample aggregation.
  - Historical baseline comparison.
- **RAG grounding**
  - Optional ChromaDB retrieval context.
- **Backtest store**
  - JSON persistence of prediction history.

---

## [1.1.0] — 2026-04-15

### Added
- **Standalone CLI** (`smf-swarm`)
  - `predict`, `benchmark`, `config`, `web` subcommands.
  - Rich terminal output with progress bars.
- **Hardware-aware adaptive scaling**
  - Auto-detects RAM, GPU, CPU; sets temperature / sampling defaults accordingly.

---

## [1.0.0] — 2026-04-10

- Initial release: Ensemble prediction engine debate-based confidence aggregation.
