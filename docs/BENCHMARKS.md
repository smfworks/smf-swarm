# SMF Swarm Benchmarks

This document describes how SMF Swarm measures and reports prediction quality. Every installation ships with a **zero-dependency benchmark** — no external API calls, no authentication tokens, no network access required.

---

## Quick Start

```bash
# Zero-dependency self-test (≈30s, no external APIs)
smf-swarm benchmark --self-test

# Run against bundled dataset with custom modes
smf-swarm benchmark --dataset bundled --modes standard,debate --max-questions 50

# Legacy: generate a synthetic dummy dataset for extended testing
python scripts/fetch_benchmark_data.py --dummy --limit 200

# Results written to benchmark_results/<run_id>/report.md
```

---

## 1. Datasets

### 1.1 Bundled Mini-Benchmark (Shipped with Package)

The package includes `mini_benchmark.jsonl` (50 questions) inside `smf_swarm/benchmarks/data/`. This dataset is automatically available and requires zero configuration.

**Properties:**
- **50 resolved binary questions** across 15 domains (technology, finance, climate, health, geopolitics, science, sports, culture, security, energy, legal, demographics, infrastructure, education, transport)
- **Known ground-truth outcomes** (outcome ∈ {0, 1}) with calibrated base rates for synthetic realism
- **No external API calls** — bundled as package data
- **Deterministic seed** (seed=20250429) for reproducible results
- **Default for `--self-test`** and `BenchmarkHarness.run(dataset="bundled")`

Use cases: CI/CD validation, customer self-test mode, quick calibration sanity checks.

### 1.2 External Datasets (Optional, R&D Only)

These sources are documented for internal R&D validation and are **not required** for product operation.

| # | Dataset | Status | Notes |
|---|---------|--------|-------|
| 1 | **Metaculus Resolved Binary Questions** | Token-gated as of April 2026 | Requires `METACULUS_API_TOKEN` env var. Free personal research token available at [metaculus.com](https://www.metaculus.com). Not shipped to customers. |
| 2 | **FiveThirtyEight MLB Elo Forecasts** | URL dead (404/redirect) | GitHub raw CSV endpoints removed. Projects.fivethirtyeight.com redirects to ABC News. Historical data may require manual archive retrieval. |
| 3 | **Good Judgment Open (GJOpen)** | Manual CSV export | Requires periodic manual export. Not automated. |

> **Product principle**: SMF Predict is packaged software with **zero runtime external dependencies**. The bundled benchmark satisfies this. External fetchers exist only for our internal comparison studies.

---

## 2. Evaluation Methodology

All predictions are mapped to a binary outcome space (`0` = event did not occur, `1` = event occurred). For numeric-range questions we first translate them into exceedance binaries.

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

### 2.2 Baselines

Every benchmark run automatically compares SMF Swarm against:

| Baseline | Description |
|----------|-------------|
| Always 50% | Constant probability 0.5 (maximally uninformative) |
| Base Rate | Historical frequency of positive outcomes in the dataset |
| LogReg TF-IDF | Text-only bag-of-words classifier (requires scikit-learn) |

### 2.3 Supplementary Metrics

- **Runtime**: wall-clock duration per prediction (`duration_s` from `PipelineResult`).
- **Health Score**: pipeline-internal diagnostic (data quality, social modifier, etc.).
- **Conformal Prediction**: optional calibrated prediction intervals with target coverage (see `--conformal`).

---

## 3. Hardware and Model Configuration

### 3.1 Hardware

| Component | Minimum Spec | Recommended Spec |
|-----------|--------------|------------------|
| CPU | 8 vCPU cores | 16 vCPU cores (for parallel Debate / Social nodes) |
| RAM | 16 GB | 32 GB |
| Disk | 50 GB SSD | 200 GB SSD (for SQLite backtest DB + ChromaDB RAG cache) |
| GPU | Optional | 1× NVIDIA A10G / A100 40 GB (if serving local LLM instead of API) |

> **Reproducibility**: Record exact `instance_type` and `cpuinfo` at benchmark start via `scripts/log_hw_env.py` (enabled with `--hw-env`).

### 3.2 LLM Configuration

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Model | `gpt-4o-2024-08-06` (or pinned snapshot) | Strong reasoning + deterministic JSON parsing |
| Temperature | `0.2` (base) | low randomness for single runs; multi-sample sweeps for uncertainty |
| Max tokens | `2,048` | Sufficient for report generation without truncation |
| Context window | `128k` | Needed for long RAG chunks + debate transcripts |

### 3.3 Pipeline Hyperparameters

| Mode | Multi-Sample | `social_agents` | `social_rounds` | Notes |
|------|--------------|-----------------|-----------------|-------|
| `naive` / `simple` | `1` | — | — | Baselines only |
| `standard` | `1` and `5` | — | — | Two sub-variants reported |
| `debate` | `1` and `5` | — | — | 3 agents × 2 rounds (ThreadPoolExecutor) |
| `full` | `1` and `5` | `5` | `3` | Includes social simulation |

---

## 4. Results Format

Each benchmark run writes:
- `report.json` — machine-readable metrics and per-question results
- `report.md` — human-readable summary with tables and reliability plots
- `plots/*.png` — reliability diagrams per mode

### 4.1 Example Report Snippet

```markdown
## SMF Swarm Benchmark — mini_benchmark

| Mode | Brier | ECE | Accuracy | Avg Duration |
|------|-------|-----|----------|--------------|
| standard_ms1 | 0.2478 | 0.0891 | 0.60 | 1.2s |
| debate_ms1 | 0.2312 | 0.0743 | 0.64 | 3.4s |

**Baselines:**
- Always 50%: Brier = 0.2500
- Base Rate: Brier = 0.1984
- LogReg TF-IDF: Brier = 0.2651 *(scikit-learn required)*
```

---

## 5. Programmatic API

```python
from smf_swarm.benchmarks.harness import BenchmarkHarness

harness = BenchmarkHarness(llm_model="gpt-4o-2024-08-06")

# Zero-dependency bundled dataset
report = harness.run(
    dataset="bundled",
    modes=["standard", "debate"],
    multi_samples=[1],
    output_dir="benchmark_results/",
)

# External dataset (if you have a Metaculus token)
report = harness.run(
    dataset="~/.cache/smf-swarm/benchmarks/metaculus.jsonl",
    modes=["standard", "debate", "full"],
    multi_samples=[1, 5],
    output_dir="benchmark_results/",
    max_questions=500,
    conformal_alpha=0.05,
)

report.to_markdown("benchmark_results/latest.md")
```

---

## 6. External Data Fetchers (R&D Only)

The `scripts/fetch_benchmark_data.py` script fetches live data for our internal comparison studies. It is **not invoked during normal product operation**.

```bash
# Fetch Metaculus (requires METACULUS_API_TOKEN)
python scripts/fetch_benchmark_data.py --datasets metaculus --limit 200

# All datasets (Metaculus + 538 MLB)
python scripts/fetch_benchmark_data.py --datasets metaculus,538mlb --limit 500
```

> **Note**: FiveThirtyEight MLB Elo endpoints are dead as of April 2026 (404 or redirect to ABC News). Metaculus requires a personal research token. These fetchers are maintained on a best-effort basis for internal R&D.

---

## 7. Changelog

| Date | Change |
|------|--------|
| 2026-04-29 | Added bundled `mini_benchmark.jsonl` (50 questions, 15 domains). Default `--dataset bundled`. Added `--self-test` flag. Marked Metaculus and 538 fetchers as R&D-only due to API auth / dead URLs. |
