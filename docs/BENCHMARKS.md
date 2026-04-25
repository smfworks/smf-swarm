# SMF Swarm Benchmarks

This document outlines a reproducible benchmarking protocol for evaluating SMF Swarm prediction quality against publicly available forecasting datasets. The goal is to measure probabilistic accuracy, calibration, and runtime cost across the three pipeline modes (`standard`, `debate`, `full`).

---

## 1. Dataset Selection Criteria

Selected datasets must satisfy the following criteria:

- **Publicly accessible** with a permissible license (or API) for research use.
- **Resolved ground truth** so that forecasts can be scored against real outcomes.
- **Diverse domains** to test generalization across science, geopolitics, and macro-social questions.
- **Compatible with probabilistic output** (confidence in `[0, 1]`) to enable Brier-score and calibration analysis.
- **Minimum 500 resolved questions** to ensure statistically significant metric estimates.

### 1.1 Selected Datasets

| # | Dataset | Domain | URL | Description |
|---|---------|--------|-----|-------------|
| 1 | **Metaculus Resolved Binary Questions** | Science & Technology | <https://www.metaculus.com/api2/> | Community forecasting platform with thousands of resolved binary questions. Each question has a crowd consensus and a final `0/1` outcome. We query the API for `status=resolved` and `type=binary`. |
| 2 | **Good Judgment Open (GJOpen)** | Geopolitics & Social | <https://www.gjopen.com/questions/> + periodic CSV exports | Tournament-grade geopolitical forecasts. Questions are binary or numeric-range. We derive binary sub-questions from numeric items (e.g., "Will X exceed threshold Y by date Z?"). |
| 3 | **FiveThirtyEight MLB Elo Forecasts** | Sports (Time-Series) | <https://github.com/fivethirtyeight/data/tree/master/mlb-elo> | Historical game-level predictions with model-generated win probabilities and actual outcomes. Useful for stress-testing calibration on highly stochastic, high-frequency events. |

> **Data extraction script**: `scripts/fetch_benchmark_data.py` pulls records via the Metaculus API (authenticated), parses FiveThirtyEight CSVs, and writes a canonical JSONL schema:
>
> Usage:
> ```bash
> # Fetch live data
> python scripts/fetch_benchmark_data.py --datasets metaculus,538mlb --limit 500
>
> # Generate synthetic data for testing
> python scripts/fetch_benchmark_data.py --dummy --limit 200
> ```
>
> JSONL schema:
> ```json
> {"id": "...", "question_text": "...", "domain": "...", "outcome": 0|1, "resolved_at": "...", "source": "...", "url": "..."}
> ```
>
> Benchmark harness:
> ```bash
> # Run SMF Swarm against a dataset
> smf-swarm benchmark --dataset dummy --modes standard,debate,full --multi-samples 1,5 --hw-env
>
> # Results written to benchmark_results/<run_id>/report.md
> ```

---

## 2. Evaluation Methodology

All predictions are mapped to a binary outcome space (`0` = event did not occur, `1` = event occurred). For numeric-range questions we first translate them into exceedance binaries as described in §1.1.

### 2.1 Core Metrics

- **Brier Score (BS)**
  - Formula: `BS = (1/N) Σ (p_i – o_i)²` where `p_i` is the predicted confidence and `o_i` is the realized outcome (`0` or `1`).
  - Range: `0` (perfect) to `1` (worst).
  - Reported both per-dataset and pooled across all datasets.

- **Calibration (Reliability & ECE)**
  - Construct `M=10` equal-width bins over predicted confidence `[0, 1]`.
  - **Expected Calibration Error (ECE)**: weighted average of the gap between bin accuracy and mean predicted probability.
  - **Max Calibration Error (MCE)**: maximum gap across bins.
  - Produce reliability diagrams: `plots/calibration_<dataset>_<mode>.png`.

- **Accuracy**
  - Threshold the confidence at `0.5`: predict `1` if `p_i ≥ 0.5`, else `0`.
  - Report **Accuracy**, **Precision**, **Recall**, and **F1**.

### 2.2 Supplementary Metrics

- **Logarithmic Loss** (for probabilistic sharpness).
- **Net Brier Skill Score (BSS)** relative to the historical base rate.
- **Runtime**: wall-clock duration per prediction (`duration_s` from `PipelineResult`).
- **Cost**: estimated token spend per mode (input + output tokens × price).

### 2.3 Evaluation Harness

A helper class `BenchmarkHarness` (future `src/smf_swarm/benchmarks/harness.py`) will:

1. Load the canonical dataset.
2. Iterate rows and call `Pipeline.run(query=question_text, mode=<mode>, domain=<domain>)`.
3. Extract `confidence` from the returned `PipelineResult`. If multi-sample is enabled, use `confidence_mean`.
4. Record: `prediction_id`, `mode`, `confidence`, `outcome`, `duration_s`, `health_score`, `data_quality`, `social_modifier`.
5. Persist to the existing SQLite backtest store (`BacktestStore`) under a `benchmarks` tag.
6. After the run, compute all metrics and emit JSON + Markdown report.

---

## 3. Hardware and Model Configuration

### 3.1 Hardware

| Component | Minimum Spec | Recommended Spec |
|-----------|--------------|------------------|
| CPU | 8 vCPU cores | 16 vCPU cores (for parallel Debate / Social nodes) |
| RAM | 16 GB | 32 GB |
| Disk | 50 GB SSD | 200 GB SSD (for SQLite backtest DB + ChromaDB RAG cache) |
| GPU | Optional | 1× NVIDIA A10G / A100 40 GB (if serving local LLM instead of API) |

> **Reproducibility requirement**: Record exact `instance_type` and `cpuinfo` at benchmark start via `scripts/log_hw_env.py`.

### 3.2 LLM Configuration

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Model | `gpt-4o-2024-08-06` (or pinned snapshot) | Strong reasoning + deterministic JSON parsing |
| Temperature | `0.2` (base) | Low randomness for single runs; §3.3 for multi-sample |
| Max tokens | `2,048` | Sufficient for report generation without truncation |
| Context window | `128k` | Needed for long RAG chunks + debate transcripts |

### 3.3 Pipeline Hyperparameters

| Mode | Multi-Sample | `social_agents` | `social_rounds` | Notes |
|------|--------------|-----------------|-----------------|-------|
| `naive` / `simple` | `1` | — | — | Baselines only |
| `standard` | `1` and `5` | — | — | Two sub-variants reported |
| `debate` | `1` and `5` | — | — | 3 agents × 2 rounds (ThreadPoolExecutor) |
| `full` | `1` and `5` | `6` | `3` | Standard + Debate → Merge → Social Simulator |

- **RAG**: ChromaDB `persistent_directory=./chroma_benchmark` with `embedding_model=text-embedding-3-small` and `chunk_size=512`.
- **SQLite Backtest DB**: `backtest_store.db` with schema extended by `benchmarks` table via `BacktestStore`.

---

## 4. Baseline Comparisons

Every benchmark run must include the following baselines alongside the three SMF Swarm modes.

### 4.1 Naïve Baselines

| Baseline | Method | Rationale |
|----------|--------|-----------|
| **Always 50%** | Predict `0.5` for every question. | Tests whether the pipeline extracts any signal at all. |
| **Historical Base Rate** | Predict the dataset’s empirical outcome frequency. | Stronger naïve baseline; measures lift above marginal probability. |

### 4.2 Simple Model Baseline

- **Logistic Regression on TF-IDF**:
  - Vectorize `question_text` using `sklearn.feature_extraction.text.TfidfVectorizer(max_features=5,000)`.
  - Train `sklearn.linear_model.LogisticRegression(max_iter=1,000)` on the training split.
  - Output probability of class `1`.
- **Why**: Tests whether raw linguistic patterns in the question text alone suffice, isolating the value of external search/RAG/debate.

### 4.3 SMF Swarm Modes

| Mode | Abbreviation | Description |
|------|--------------|-------------|
| **Standard** | `STD` | `gather → engineer → reflect → model → validate → report` |
| **Debate** | `DEB` | `gather → engineer → debate (3 agents × 2 rounds) → report` |
| **Full** | `FULL` | `STD + DEB → merge → social simulation → report` |

Each mode is evaluated at:
- `multi_sample=1` (single deterministic pass)
- `multi_sample=5` (temperature-perturbed ensemble; use `confidence_mean`)

> **Backtesting integration**: All runs write to `BacktestStore.record(...)` so that future runs can compute time-decayed calibration.

---

## 5. Results Table Template

After each benchmark run, populate the tables below and commit the updated `docs/BENCHMARKS.md` or save as `docs/benchmarks_results_v<date>.md`.

### 5.1 Binary Forecasting Performance

| Dataset | Mode | N | Brier Score ↓ | ECE ↓ | Accuracy ↑ | F1 ↑ | Avg Duration (s) | Est. Cost ($) |
|---------|------|---|---------------|-------|------------|------|------------------|---------------|
| Metaculus | Always 50% | — | — | — | — | — | — | — |
| Metaculus | Base Rate | — | — | — | — | — | — | — |
| Metaculus | LogReg TF-IDF | — | — | — | — | — | — | — |
| Metaculus | STD (ms=1) | — | — | — | — | — | — | — |
| Metaculus | STD (ms=5) | — | — | — | — | — | — | — |
| Metaculus | DEB (ms=1) | — | — | — | — | — | — | — |
| Metaculus | DEB (ms=5) | — | — | — | — | — | — | — |
| Metaculus | FULL (ms=1) | — | — | — | — | — | — | — |
| Metaculus | FULL (ms=5) | — | — | — | — | — | — | — |
| GJOpen | … | — | — | — | — | — | — | — |
| 538 MLB | … | — | — | — | — | — | — | — |

*(ms = multi_sample)*

### 5.2 Calibration Summary

| Dataset | Mode | ECE | MCE | Reliability Diagram Path |
|---------|------|-----|-----|--------------------------|
| Metaculus | STD (ms=1) | — | — | `plots/metaculus_std_ms1_reliability.png` |
| Metaculus | FULL (ms=5) | — | — | `plots/metaculus_full_ms5_reliability.png` |
| … | … | — | — | … |

### 5.3 Runtime & Health

| Mode | Avg Duration (s) | 95th Percentile (s) | Health Score ↓ | Data Quality ↑ | Social Modifier |
|------|------------------|----------------------|----------------|------------------|------------------|
| STD (ms=1) | — | — | — | — | — |
| STD (ms=5) | — | — | — | — | — |
| DEB (ms=1) | — | — | — | — | — |
| DEB (ms=5) | — | — | — | — | — |
| FULL (ms=1) | — | — | — | — | — |
| FULL (ms=5) | — | — | — | — | — |

### 5.4 Win Rates (Pairwise Mode Comparison)

A mode is counted as a "win" on a given question if its Brier score is lower than the competing mode. Report win rates as fractions.

| Comparison | Metaculus | GJOpen | 538 MLB |
|------------|-----------|--------|---------|
| STD vs. Base Rate | — | — | — |
| DEB vs. STD | — | — | — |
| FULL vs. DEB | — | — | — |
| ms=5 vs. ms=1 (same mode) | — | — | — |

---

## Appendix A — Reproducibility Checklist

- [ ] Pinned LLM snapshot (`gpt-4o-2024-08-06` or equivalent commit hash / local model weights).
- [ ] `smf_swarm` version tag recorded (e.g., `v1.3.0`).
- [ ] `pyproject.toml` dependencies installed from lockfile (`poetry.lock` or `requirements-frozen.txt`).
- [ ] `temperature`, `max_tokens`, and `multi_sample` values logged.
- [ ] ChromaDB directory and embedding model version recorded.
- [ ] Hardware `instance_type` and CPU/GPU info saved.
- [ ] Random seed set for any stochastic baseline models (e.g., `random_state=42` for LogReg).
- [ ] SQLite backtest DB path noted and archived.

## Appendix B — Changelog

- **2026-04-24** — Initial benchmark outline drafted.

