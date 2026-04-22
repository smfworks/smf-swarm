# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[1.0.1]: https://github.com/smfworks/smf-swarm/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/smfworks/smf-swarm/releases/tag/v1.0.0
