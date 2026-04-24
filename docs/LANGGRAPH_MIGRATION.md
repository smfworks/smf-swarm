# LangGraph Migration Feasibility Study

> **Date:** 2026-April-24  
> **Analyst:** Liam Hermes, CDO SMF Works  
> **Scope:** Phase 4 — Strategic Architecture Review  
> **Source:** `src/smf_swarm/langgraph_study.py` (functional prototype)  

---

## 1. Executive Summary

The existing `_run_state_machine` in `pipeline.py` is a clean sequential Python function with conditional branches and one retry loop. **It maps almost 1:1 to LangGraph's `StateGraph`**.

Conclusion: **Migration is technically trivial, strategically high-value, and carries near-zero regression risk.** The migration is additive — the sequential fallback remains active until LangGraph is battle-tested.

| Criterion | Assessment |
|-----------|------------|
| Node mapping effort | Low — every underscore method wraps in ~5 lines |
| Conditional routing | Low — 4 router functions cover all branches |
| Persistence value | High — resume mid-pipeline after crash |
| Streaming value | High — native `.stream()` replaces manual SSE |
| Retry policy value | Medium — per-node automatic retries |
| Human-in-the-loop | High — pause at validator for approval |
| Parallel branches | Already implemented (ThreadPoolExecutor); LangGraph adds Map-Reduce for future multi-sample |
| Risk | Low — fallback to `_run_state_machine` via `LANGGRAPH_DISABLE=1` |
| Estimated effort | 2–4 weeks (1 FTE) |

---

## 2. Current Architecture Mapping

### 2.1 Nodes (Sequential Flow)

```
START → data_gatherer → feature_engineer → statistical_baseline
                                      ↓
                              [Router: mode?]
                              ├─ standard → reflection → model_runner → validator
                              │                            ↑← retry_model ─┘
                              │                            ↓
                              │                         [Router: pass?]
                              │                              ├─ pass → reporter
                              │                              └─ fail (1 retry) → model_runner
                              ├─ debate ───────────────────→ debate ──→ reporter
                              └─ full → reflection → model_runner → validator
                                                      ↓
                                                   [Router: pass?]
                                                      └─ pass → debate → merge
                                                                      ↓
                                                                   [Router: social?]
                                                                      ├─ yes → social → reporter
                                                                      └─ no  → reporter
```

### 2.2 Mapped Nodes

| Current Method | LangGraph Node Name | Notes |
|----------------|--------------------|-------|
| `_data_gatherer` | `data_gatherer` | Can be ToolNode in future |
| `_feature_engineer` | `feature_engineer` | Pure LLM call |
| `_statistical_baseline` | `statistical_baseline` | Skips gracefully if no extras |
| `_reflection` | `reflection` | CoT reasoning extraction |
| `_model_runner` | `model_runner` | Core prediction |
| `_validator` | `validator` | LLM-based PASS/FAIL |
| (internal retry) | `retry_model` | Re-runs `model_runner` |
| `DebateEngine.run()` | `debate` | Already parallelized inside |
| `_merge` | `merge` | Weighted consensus for Full mode |
| `SocialSimulator.run()` | `social` | Sentiment trajectory output |
| `_reporter` | `reporter` | Final structured report |

### 2.3 Conditional Routers

| Router | Source Node | Condition | Destinations |
|--------|-------------|-----------|--------------|
| `_router_after_baseline` | `statistical_baseline` | `mode` | `reflection` / `debate` / `reporter` (fail-fast) |
| `_router_after_validate` | `validator` | `validation_passed` + `iteration` + `mode` | `reporter` / `retry_model` / `debate` |
| `_router_after_retry` | `retry_model` | Always | `validator` |
| `_router_after_debate` | `debate` | `mode` | `reporter` (debate) / `merge` (full) |
| `_router_after_merge` | `merge` | `run_social` | `social` / `reporter` |

---

## 3. LangGraph Advantages Over Current `_run_state_machine`

### 3.1 Persistence (High Value)

- **Current:** If the CLI or web server crashes mid-pipeline, the entire run is lost.
- **LangGraph:** `MemorySaver()` or `SqliteSaver()` checkpoints state after every node. Resume from the last successful node.
- **Impact:** A cancelled 40-minute Full mode run can resume at minute 25 instead of restarting.

### 3.2 Streaming (High Value)

- **Current:** The web UI manually dispatches SSE events inside each node method. This is brittle and hard to test.
- **LangGraph:** `graph.stream()` emits `{node_name: updates}` natively. The web UI adapter becomes a 15-line for-loop over the stream.
- **Impact:** Web SSE becomes robust, testable, and eliminates ~200 lines of manual event dispatch code.

### 3.3 Retries (Medium Value)

- **Current:** One manual retry on validator failure.
- **LangGraph:** `RetryPolicy(max_attempts=2)` per node. Can independently retry `model_runner`, `debate`, etc.
- **Impact:** Automatically handles transient LLM timeouts without custom logic.

### 3.4 Human-in-the-Loop (High Value)

- **Current:** No pause mechanism. Once started, the pipeline runs to completion.
- **LangGraph:** `interrupt_after=["validator"]` pauses execution and waits for human approval before continuing.
- **Impact:** Operator can inspect the prediction before committing to expensive debate + social stages.

### 3.5 Parallel Branches (Future Value)

- **Current:** Debate openings are parallel via `ThreadPoolExecutor`. Multi-sample is sequential.
- **LangGraph:** Map-Reduce pattern can run all multi-sample predictions in parallel, collect results, and merge.
- **Impact:** Multi-sample mode drops from N×sequential to fan-out + reduce, halving wall-clock time.

### 3.6 Observability (Medium Value)

- **Current:** `SwarmMonitor` tracks node timings in-memory.
- **LangGraph:** Native `draw_mermaid()` for diagrams, `LangSmith` tracing compatible.
- **Impact:** Professional documentation and debugging support.

---

## 4. Migration Plan

### Phase A — Infrastructure (Week 1)

1. Add `[langgraph]` extra to `pyproject.toml`:
   ```toml
   langgraph = ["langgraph>=0.3.0"]
   ```
2. Add `[langgraph]` deps to `Dockerfile` / `docker-compose.yml`.
3. Create `src/smf_swarm/langgraph_study.py` (Done — functional prototype).
4. Write unit tests for each wrapper node in isolation (mock LLM responses).

### Phase B — Web UI SSE Adapter (Week 1–2)

1. Add `/api/predict/langgraph` endpoint that uses `graph.stream()`.
2. SSE event adapter: iterate stream → emit `node_complete` → same frontend format.
3. Verify history/compare/settings modals all work unchanged.

### Phase C — Backtest Integration (Week 2)

1. Persist `thread_id` and checkpoint path in `BacktestStore`.
2. Add `langgraph_checkpoint` column to SQLite.
3. Resume any backtested run from its checkpoint for audit.

### Phase D — Parallel Multi-Sample (Week 3)

1. Replace sequential `_multi_sample_run` with LangGraph Map-Reduce.
2. Fan-out N temperature-swept nodes → reduce to mean + std.
3. A/B test: sequential vs. parallel on 20 identical queries.

### Phase E — Soft Switch (Week 4)

1. Default `Pipeline.run()` delegates to `LangGraphPipeline` when `langgraph` is installed.
2. Environment variable `LANGGRAPH_DISABLE=1` forces legacy path.
3. Update `README.md`, `ARCHITECTURE.md`, release v1.4.0.

### Phase F — Cleanup (Week 4+)

1. Deprecate manual SSE dispatch in `jobs.py`.
2. Remove `ThreadPoolExecutor` from debate engine (LangGraph handles parallelism).
3. Migrate `SwarmMonitor` to LangGraph hooks for unified observability.

---

## 5. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| LangGraph API changes between 0.3 → 1.0 | Medium | Medium | Pin `langgraph>=0.3,<0.4` in pyproject.toml |
| Performance regression in single-node LLM latency | Low | High | A/B test before default switch; fallback always available |
| State serialization failures with large LLM outputs | Low | Medium | Truncate/paginate state fields >16KB; add `__dict__` filter |
| Dependency bloat for users who only want CLI | Low | Low | `[langgraph]` is optional; core stays lightweight |
| Web UI race conditions with checkpointed state | Low | Medium | Use unique `thread_id` per web run; isolate checkpoint DB per user |

---

## 6. File Inventory

| File | Status | Description |
|------|--------|-------------|
| `src/smf_swarm/langgraph_study.py` | ✅ Prototype | Full adapter, routers, graph builder, migration effort comment block |
| `pyproject.toml` | ⏳ Pending | Add `[langgraph]` extra |
| `src/smf_swarm/web/api.py` | ⏳ Pending | `/api/predict/langgraph` endpoint |
| `docs/LANGGRAPH_MIGRATION.md` | ✅ Done | This document |

---

*Feasibility study complete. Phase A can begin immediately when authorized.*
*Liam Hermes, CDO, SMF Works.*
