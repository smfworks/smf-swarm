# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.4.1] — 2026-04-24

### Fixed
- **LangGraph `StateGraph.compile()` compatibility** (`src/smf_swarm/pipeline_langgraph.py`)
  - Removed deprecated `retry=` kwarg from `compile()`; modern LangGraph (≥0.3) applies retry policies per-node via `add_node(retry_policy=...)`.
  - Fixes `TypeError: compile() got unexpected keyword argument 'retry'` on current LangGraph stable.
- **Test suite green** — 4 auto-generated test bugs fixed:
  - Missing `import pytest` in 4 test files (collection failure).
  - `graph.draw_mermaid()` → `graph.get_graph().draw_mermaid()` (API path change).
  - MagicMock auto-creation of `_debate` attribute neutralized (`p._debate = None` in fixture).
  - Unknown-node timing test corrected (early return means no `node_timings` entry).
- **Version bump**: `1.4.0` → `1.4.1`.

### Security
- No dependency changes.

---

## [1.4.0] — 2026-04-24

### Added
- **LangGraph Execution Backend** (optional `[langgraph]` extra — `pip install smf-swarm[langgraph]`)
  - New `src/smf_swarm/pipeline_langgraph.py`: production `StateGraph` adapter.
    - `SwarmState` (TypedDict) with 30+ fields.
    - `_make_node()` factory wrapping every Pipeline node method.
    - `build_pipeline_graph()`: 12 nodes + 5 conditional routers + interrupt_after validator + `MemorySaver` checkpointing + `RetryPolicy(max_attempts=2)`.
    - `LangGraphPipeline`: `.run()`, `.stream()`, `.resume()` with checkpoint recovery.
    - `MultiSamplePipeline`: `Map-Reduce` fan-out for temperature-swept runs (3–5 samples) → mean + std confidence.
    - `create_pipeline()` factory with `LANGGRAPH_AUTO` / `LANGGRAPH_DISABLE` env vars.
  - 4 unit-test files: `test_langgraph_nodes.py`, `test_langgraph_routing.py`, `test_langgraph_pipeline.py`, `test_langgraph_integration.py`.
- **Web SSE Adapter for LangGraph**
  - `src/smf_swarm/web/jobs.py`: `_run_job_langgraph()` maps `stream_callback` to SSE — identical event surface as classic mode.
  - `src/smf_swarm/web/api.py`: `/api/predict` accepts `"langgraph": true`; new `/api/predict/langgraph` endpoint returns 503 if LangGraph not installed.
- **Backtest Integration with Checkpoint Metadata**
  - `src/smf_swarm/backtest.py`: schema extended with `langgraph INTEGER`, `thread_id TEXT`, `checkpoint_path TEXT`; index `idx_pred_thread`.
  - `src/smf_swarm/pipeline.py`: `_backtest.record()` passes metadata.
- **Soft Switch**
  - `Pipeline.run(..., langgraph=None)` auto-detects when `LANGGRAPH_AUTO=1` and `[langgraph]` is installed.
  - `Pipeline.run(..., langgraph=True)` forces LangGraph. `Pipeline.run(..., langgraph=False)` forces classic.
  - CLI flag `--langgraph` on `smf-swarm predict`.
- **Deprecation**
  - `src/smf_swarm/langgraph_study.py` deprecated; production code lives in `pipeline_langgraph.py`.

### Changed
- `pyproject.toml`: added `[langgraph]` extra (`langgraph>=0.3.0`).
- `src/smf_swarm/pipeline.py`: `run()` `langgraph` parameter changed from `bool = False` to `bool | None = None` for tri-state logic.
- `docs/ARCHITECTURE.md`: module tree updated for v1.2–v1.4 modules.

---

## [1.3.0] — 2026-04-24

### Added
- **Multi-Sample Uncertainty**: `Pipeline.run(..., multi_sample=N)` runs the full pipeline N times at varied temperatures (base ±0.15 per step, bounded 0.1–0.9) → mean confidence, std confidence, and representative state (closest to mean). CLI flag `--multi-sample`.
- **UI Polish**
  - Charts: sentiment trajectory and confidence comparison bars (pure SVG/JS, no external dependency). Auto-rendered in Web UI on every result.
  - History + Compare mode: `localStorage`-backed run archive. History drawer with search/filter. Side-by-side compare view for two selected runs across all confidence/sentiment/health metrics.
  - Settings panel: sliders for social agents, debate rounds, temperature; toggle structured output enforce; mode/domain override.
  - PWA: `manifest.json`, offline service worker, installable icons. Works offline after initial page load.
  - CLI rich dashboard: optional `smf-swarm predict --live` for a `rich.live.Live` panel with real-time progress bars, per-node timing, and live ETA.

### Changed
- `pyproject.toml`: split optional deps into `[predict]`, `[trust]`, `[rag]`, `[dev]`, `[cli]`.
- `src/smf_swarm/pipeline.py`: added `_multi_sample_run()`, `_statistical_baseline`.
- `src/smf_swarm/cli.py`: added `--multi-sample`, `--live` flags.

---

## [1.2.0] — 2026-04-24

### Added
- **Predictive Baselines** (optional `[predict]` extras)
  - New `src/smf_swarm/predict/baseline.py`: `StatisticalBaseline` with Prophet → ARIMA → polynomial fallback. Lazy loads, graceful skip if extras absent.
- **Tool Calling**: `duckduckgo_search` and `restricted-repl` Python execution injected into data gatherer. Optional `duckduckgo-search` dep.
- **Local RAG** (optional `[rag]` extras): `RAGStore` with ChromaDB + `all-MiniLM-L6-v2`. Auto-injected into data gatherer when documents uploaded.
- **Backtesting / Calibration**: `BacktestStore` backed by SQLite. Auto-records on every run. `smf-swarm backtest` CLI command with domain/mode filters and ground-truth `--set-truth`.

### Changed
- `pyproject.toml`: `[predict]`, `[trust]`, `[rag]`, `[dev]` optional-dep groups.

---

## [1.1.0] — 2026-04-24

### Added
- **Trust / Security**
  - API keys stored in OS keyring (optional `keyring` dep). Config file stores placeholder + `chmod 0o600` enforced.
  - Pydantic structured output extraction replacing regex. Hardened regex fallback.
  - Web UI optional bearer-token auth + in-memory rate limiting.
- **Performance**
  - Disk-based LLM response caching (24 h TTL). `--no-cache` flag.
  - Parallel debate openings via `ThreadPoolExecutor`.
  - Per-node ETA estimates.
- **Install / Packaging**
  - `Dockerfile` + `docker-compose.yml` with Ollama sidecar.
  - `install.sh` auto-detects OS, can install Ollama, recommends `pipx` or auto-creates venv.
- **Docs** updated to describe "custom sequential hybrid pipeline" accurately.

### Changed
- `pyproject.toml`: `[trust]`, `[web]`, `[dev]` optional deps.

---

## [1.0.1] — 2026-04-21

### Fixed
- Debate engine anchoring bias: judge randomizes presentation order.
- Asymmetric text budgets: openings 1500 chars, rebuttals 1000 chars for all positions.
- Dead-code dissent surfaced in `PipelineResult.dissent`.

---

## [1.0.0] — 2026-04-21

### Added
- Initial release: Standard, Debate, Full+Social modes.
- LLM-agnostic: Ollama, OpenAI, Anthropic, any OpenAI-compatible endpoint.
- Hardware-aware scaling, structured JSON output, health monitoring.

---

[1.4.0]: https://github.com/smfworks/smf-swarm/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/smfworks/smf-swarm/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/smfworks/smf-swarm/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/smfworks/smf-swarm/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/smfworks/smf-swarm/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/smfworks/smf-swarm/releases/tag/v1.0.0
