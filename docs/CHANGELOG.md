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
- **Version bump:** `1.4.0` → `1.4.1`.

### Security
- No dependency changes.

---

## [1.4.0] — 2026-04-24

### Added
- **LangGraph Execution Backend** (optional `[langgraph]` extra — `pip install smf-swarm[langgraph]`)
  - New `src/smf_swarm/pipeline_langgraph.py`: production `StateGraph` adapter.
    - `SwarmState` (TypedDict) with 30+ fields mirroring PipelineResult.
    - `_make_node()` factory wrapping every Pipeline node method (~5 lines per node).
    - `build_pipeline_graph()`: compiles 12 nodes + 5 conditional routers + interrupt_after validator + `MemorySaver` checkpointing + `RetryPolicy(max_attempts=2)`.
    - `LangGraphPipeline` class: `.run()` with `stream_callback`, `.resume()` from checkpoint, `.stream()` generator for SSE.
    - `create_pipeline()` factory: `LANGGRAPH_AUTO=1` enables auto-detect; `LANGGRAPH_DISABLE=1` forces classic path.
  - Unit test suite:
    - `tests/test_langgraph_nodes.py` — 22 tests covering all 12 node wrappers, timing, ok-short-circuit.
    - `tests/test_langgraph_routing.py` — 5 router families, 20+ boundary state combinations.
    - `tests/test_langgraph_pipeline.py` — constructor, run(), multi_sample fallback, stream_callback, resume(), create_pipeline() factory.
    - `tests/test_langgraph_integration.py` — graph compilation, structural parity with classic Pipeline.
- **Web SSE Adapter for LangGraph**
  - `src/smf_swarm/web/jobs.py`: `_run_job_langgraph()` maps `stream_callback` node events to SSE `JobEvent` progress events (identical surface as classic mode).
  - `src/smf_swarm/web/api.py`: `/api/predict` accepts `"langgraph": true`; new dedicated `/api/predict/langgraph` endpoint returns 503 if LangGraph not installed.
- **Backtest Integration with Checkpoint Metadata**
  - `src/smf_swarm/backtest.py`: schema extended with `langgraph INTEGER`, `thread_id TEXT`, `checkpoint_path TEXT`; index `idx_pred_thread`.
  - `src/smf_swarm/pipeline.py`: `_backtest.record()` passes `langgraph` and `thread_id` from `result.metadata`.
- **Soft Switch**
  - `Pipeline.run(..., langgraph=None)` auto-detects when `LANGGRAPH_AUTO=1` is set and `[langgraph]` is installed.
  - `Pipeline.run(..., langgraph=True)` forces LangGraph. `Pipeline.run(..., langgraph=False)` forces classic.
  - CLI flag `--langgraph` on `smf-swarm predict` enables LangGraph backend per-run.
- **Deprecation**
  - `src/smf_swarm/langgraph_study.py` marked deprecated; production code lives in `pipeline_langgraph.py`.

### Changed
- `pyproject.toml`: added `[langgraph]` extra (`langgraph>=0.3.0`).
- `src/smf_swarm/pipeline.py`: `run()` `langgraph` parameter changed from `bool = False` to `bool | None = None` for tri-state logic (True/False/Auto).
- `docs/ARCHITECTURE.md`: module tree updated to include `pipeline_langgraph.py` and all v1.2–v1.4 modules.

### Deprecated
- `src/smf_swarm/langgraph_study.py` — import triggers `DeprecationWarning`. Use `pipeline_langgraph.py`.

---

## [1.3.0] — 2026-04-24

### Added
- **Web UI Charts**
  - Pure SVG chart engine (`src/smf_swarm/web/static/js/charts.js`): zero external deps, zero CDNs.
  - `renderLineChart()` for sentiment trajectory across social rounds.
  - `renderBarChart()` for multi-sample confidence distribution.
  - Auto-rendered on result display when data is available; hidden otherwise.
- **Run History / Compare Mode**
  - `src/smf_swarm/web/static/js/history.js`: localStorage-backed run archive (max 100 entries).
  - History modal with search, domain/mode filters, checkbox-select for compare.
  - Compare modal: side-by-side column layout + word-level diff view (red strike + green add).
  - "Load" button to restore any historical run into the current UI.
  - Auto-saved every run unless "Auto-save to History" toggle is disabled.
- **Advanced Settings Panel**
  - Modal with sliders: Social Agents (5–30), Social Rounds (2–8), Temperature (0.1–0.9), Multi-Sample (1–10).
  - Toggles: LLM Cache enable/disable, Auto-save to History.
  - Custom Persona Template textarea for prompt override.
  - All settings persisted in localStorage; reset to defaults available.
- **PWA Support**
  - `manifest.json`: standalone display, theme color `#0a0a0f`, 192/512 PNG icons.
  - `sw.js`: caches static assets (HTML/CSS/JS); API calls excluded from cache.
  - Service worker registration in `main.js` init.
  - Apple PWA meta tags: `apple-mobile-web-app-capable`, `apple-mobile-web-status-bar-style`.
- **CLI Rich Rendering** (optional `[cli]` extra)
  - `src/smf_swarm/cli_rich.py`: `run_prediction_rich()` live dashboard using `rich`.
  - Panels: header (query/mode/domain), progress bar with ETA, per-node status table, final result summary.
  - `--rich` flag on `smf-swarm predict` to activate when `rich >= 13` is installed.
  - Fallback to plain text if `rich` not available.
- **CSS Expansion**
  - 450+ new lines for chart containers, modals, history filters, compare grid, diff highlights, sliders, toggles, settings, icon buttons.

### Changed
- `pyproject.toml`: new optional dep group `[cli]` → `rich>=13.0.0`.
- `src/smf_swarm/web/jobs.py`: Job dataclass gains `multi_sample` field; `_result_to_dict` now includes `sentiment_trajectory`, `multi_sample`, `baseline` for downstream rendering.
- `src/smf_swarm/web/api.py`: `/api/predict` endpoint accepts `multi_sample` parameter (validated 1–20).
- `src/smf_swarm/web/static/index.html`: modal overlays (History, Compare, Settings), manifest link, meta tags, settings button, history button.
- `src/smf_swarm/web/static/js/main.js`: ELS extended; `displayResult()` triggers chart rendering and `saveToHistory()`.
- `src/smf_swarm/web/static/css/main.css`: from 764 to ~1210 lines; modal system, history/compare/settings layouts, range slider styling, toggle switches.

---

## [1.2.0] — 2026-04-24

### Added
- **Predictive Baselines** (optional `[predict]` extras)
  - `prophet>=1.1.0`, `statsmodels>=0.14.0`, `scikit-learn>=1.3.0` listed in `pyproject.toml` under `[project.optional-dependencies]`.
  - New module `src/smf_swarm/predict/baseline.py`: `StatisticalBaseline` class.
    - Automatically detects and lazily loads Prophet, statsmodels, scikit-learn.
    - Extracts time-series data from raw text (date:value pairs or JSON arrays).
    - Running order: Prophet (≥5 pts) → ARIMA(1,1,1) (≥8 pts) → polynomial trend (≥3 pts).
    - Heuristic fallback: bullish/bearish keyword balance when no series found.
  - Integrated into pipeline as `_statistical_baseline` node after feature engineering.
    - Gracefully skips if `[predict]` extras not installed.
    - Results stored in `state["baseline"]` for downstream inspection.
- **Tool Calling for Data Gatherer**
  - New `src/smf_swarm/tools.py`: `ToolKit` class.
    - `duckduckgo_search()`: free web search via `duckduckgo-search` package (3 results by default, optional dep).
    - `python_repl()`: restricted-restricted Python execution for math/finance calculations.
  - `_data_gatherer` node now auto-injects ToolKit snippets and RAGStore context when available.
- **Local RAG** (optional `[rag]` extras)
  - New `src/smf_swarm/rag.py`: `RAGStore` class backed by ChromaDB + sentence-transformers (`all-MiniLM-L6-v2`).
    - `add_text()`, `add_pdf_text()` for chunking and ingesting documents.
    - `query()` returns top-k relevant chunks.
    - Graceful no-op if `[rag]` extras not installed.
    - RAG context auto-injected into data gatherer when documents have been uploaded.
- **Backtesting / Calibration**
  - New `src/smf_swarm/backtest.py`: `BacktestStore` backed by SQLite.
    - Schema: predictions table with query, domain, mode, confidence, ground_truth, duration, data_quality, health_score, social_modifier.
    - `record()`: every `Pipeline.run()` auto-records into backtest store (best-effort, never blocks).
    - `update_ground_truth()`: mark predictions as resolved.
    - `calibration_report()`: accuracy, Brier score, and calibration bins.
  - New CLI command: `smf-swarm backtest`.
    - `--domain`, `--mode` filters.
    - `--set-truth <id> --outcome true|false` for manual ground-truth updates.
- **Multi-Sample Uncertainty**
  - `Pipeline.run(..., multi_sample=N)` runs the full pipeline N times at varied temperatures (base ±0.15 per step, bounded 0.1–0.9).
  - Returns mean confidence, std confidence, and representative state (closest to mean).
  - CLI flag: `smf-swarm predict "..." --multi-sample 5`.
  - JSON output includes `multi_sample` dict with temperatures, confidences, mean, std.
- **CLI Improvements**
  - `--no-cache` flag on `smf-swarm predict` to bypass LLM cache.
  - `LLMCache.disable()` method for runtime cache suppression.
  - `--backtest` subcommand with calibration reporting.

### Changed
- `pyproject.toml`: split optional deps into `[predict]`, `[trust]`, `[rag]`, `[dev]`.
- `src/smf_swarm/pipeline.py`: added `_backtest`, `_baseline`, `_multi_sample_run`, `_statistical_baseline`.
- `src/smf_swarm/cli.py`: added `--multi-sample`, `--no-cache`, `--backtest` subcommand, backtest dispatch.

---

## [1.1.0] — 2026-04-24

### Added
- **Trust / Security**
  - API keys can now be stored in the OS keyring (optional `keyring` dependency). Config file stores a placeholder marker only. Graceful fallback to file-based storage with `chmod 0o600` enforced on every save.
  - Pydantic-based structured output extraction (`src/smf_swarm/structured.py`) replaces fragile regex parsing across all pipeline nodes (confidence, data quality, features, validation, report sections, sentiment). Hardened regex fallbacks remain for non-JSON outputs.
  - Web UI optional bearer-token authentication + in-memory sliding-window rate limiting (`src/smf_swarm/web/auth.py`). Warns when binding to `0.0.0.0` without auth.
- **Performance**
  - Disk-based LLM response caching with SHA-256 query+config+mode key. TTL default 24 h. Cache hits bypass all LLM calls. `--no-cache` CLI flag to force fresh run.
  - Parallel debate openings via `ThreadPoolExecutor` (Optimist + Skeptic run concurrently). ~30–40 % debate time savings.
  - Progress ETA estimates added to `SwarmMonitor`. CLI and Web UI report remaining time per node after run history is established.
- **Install / Packaging**
  - `Dockerfile` and `docker-compose.yml` for one-command deployment (`docker compose up`). Includes Ollama sidecar service and `smf-swarm` container.
  - `install.sh` now auto-detects OS and can install Ollama (Linux via official script, macOS via Homebrew). Recommends `pipx` or auto-creates a virtual environment.
- **Misc**
  - README and ARCHITECTURE.md updated to accurately describe the architecture as a "custom sequential hybrid pipeline" rather than claiming LangGraph / CrewAI integration.
  - Version bumped to `1.1.0`.

### Changed
- `pyproject.toml`: added optional dependency group `[trust]` for `keyring`, `[web]` for `flask`, `[dev]` for test/lint tools.
- `src/smf_swarm/config.py`: config save now enforces `os.chmod(config_path, 0o600)`; supports `keyring` read/write.

---

## [1.0.1] — 2026-04-21

### Fixed
- **Debate Engine anchoring bias** (`src/smf_swarm/debate/engine.py`)
  - Judge now randomizes presentation order of the three positions per-run, preventing primacy bias from always weighting Optimist heaviest.
  - Added explicit evidence-weighting instructions to the judge prompt:
    1. Independently score each position on Evidence Quality, Logical Coherence, and Factual Grounding (1-10 each).
    2. Weight by evidence quality with formal tie-breaking rules.
    3. Synthesize consensus from the highest-quality arguments.
    4. Acknowledge the strongest counter-argument and explain why it does not overturn the conclusion.
    5. Extract confidence.

- **Asymmetric text budgets** (debate engine)
  - Openings: increased from 1200/1200/1200 to **1500** chars for all three positions.
  - Rebuttals: increased from 600/600/600 to **1000** chars for all three positions.
  - Skeptic no longer structurally disadvantaged by the shortest budget.

- **Dead-code dissent** (`src/smf_swarm/debate/engine.py`, `src/smf_swarm/pipeline.py`)
  - Dissent is now surfaced in the final report: new `PipelineResult.dissent` field.
  - Reporter prompt includes `DISSENT:` section, weighted higher in the context window.
  - Users see "Why this forecast might be wrong" as a first-class output field.

- **Documentation**
  - README now clarifies standalone Swarm is CLI/API-only; points non-technical users to SMF Predict.
  - Added "Agent Integration" section documenting how to hook SMF Swarm into Hermes or OpenClaw agents, both in-process and subprocess.

### Removed
- All references to "MiroFish" replaced with "Social Swarm" across `README.md`, `pyproject.toml`, `src/smf_swarm/__init__.py`, `src/smf_swarm/social/simulator.py`, `docs/ARCHITECTURE.md`.

### Security
- No external dependency changes in this release. v1.0.1 remains MIT-only with zero AGPL/GPL code.

---

## [1.0.0] — 2026-04-21

### Added
- Initial release.
- Three prediction modes: Standard, Debate, Full+Social.
- LLM-agnostic: Ollama, OpenAI, Anthropic, or any OpenAI-compatible endpoint.
- Interactive configuration wizard (`smf-swarm configure`).
- Health monitoring per pipeline node.
- Structured JSON output with confidence, summary, risk assessment, and timestamps.
- Social simulation layer with persona templates per domain (technology, financial, political, general).

---

[1.2.0]: https://github.com/smfworks/smf-swarm/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/smfworks/smf-swarm/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/smfworks/smf-swarm/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/smfworks/smf-swarm/releases/tag/v1.0.0
