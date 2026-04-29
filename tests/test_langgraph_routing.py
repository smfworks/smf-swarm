"""Unit tests for LangGraph conditional routers.

Every router is exercised with boundary-state combinations to ensure
routing decisions are correct for all three modes (standard, debate, full)
and edge cases (retry iteration, validation failure, social enabled).
"""

from __future__ import annotations

import sys
from pathlib import Path

_repo = Path(__file__).resolve().parent.parent
_src = _repo / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from smf_swarm.pipeline_langgraph import (
    SwarmState,
    _router_after_baseline,
    _router_after_validate,
    _router_after_retry,
    _router_after_debate,
    _router_after_merge,
)

# ── Helper factories ─────────────────────────────────────────


def _base(mode: str, ok: bool = True, **kwargs) -> SwarmState:
    return {"ok": ok, "mode": mode, **kwargs}


# ── _router_after_baseline ────────────────────────────────────


class TestRouterAfterBaseline:
    def test_standard_goes_to_reflection(self):
        assert _router_after_baseline(_base("standard")) == "reflection"

    def test_debate_goes_to_debate(self):
        assert _router_after_baseline(_base("debate")) == "debate"

    def test_full_goes_to_reflection(self):
        # full starts standard sub-path, then later hits debate
        assert _router_after_baseline(_base("full")) == "reflection"

    def test_not_ok_fails_to_reporter(self):
        assert _router_after_baseline(_base("standard", ok=False)) == "reporter"

    def test_missing_mode_defaults_to_reflection(self):
        assert _router_after_baseline({"ok": True}) == "reflection"


# ── _router_after_validate ───────────────────────────────────


class TestRouterAfterValidate:
    def test_standard_pass_goes_to_reporter(self):
        st = _base("standard", validation_passed=True)
        assert _router_after_validate(st) == "reporter"

    def test_standard_fail_once_goes_to_retry(self):
        st = _base("standard", validation_passed=False, iteration=0)
        assert _router_after_validate(st) == "retry_model"

    def test_standard_fail_retry_exhausted_goes_to_reporter(self):
        st = _base("standard", validation_passed=False, iteration=2)
        assert _router_after_validate(st) == "reporter"

    def test_full_pass_goes_to_debate(self):
        st = _base("full", validation_passed=True)
        assert _router_after_validate(st) == "debate"

    def test_full_fail_goes_to_retry(self):
        st = _base("full", validation_passed=False, iteration=0)
        assert _router_after_validate(st) == "retry_model"

    def test_not_ok_goes_to_reporter(self):
        st = _base("standard", ok=False, validation_passed=False)
        assert _router_after_validate(st) == "reporter"

    def test_debate_pass_goes_to_reporter(self):
        # debate mode doesn't have validator in its path, but if routed here
        st = _base("debate", validation_passed=True)
        assert _router_after_validate(st) == "reporter"


# ── _router_after_retry ───────────────────────────────────────


class TestRouterAfterRetry:
    def test_always_back_to_validator(self):
        for mode in ("standard", "debate", "full"):
            assert _router_after_retry(_base(mode)) == "validator"


# ── _router_after_debate ──────────────────────────────────────


class TestRouterAfterDebate:
    def test_debate_mode_goes_to_reporter(self):
        assert _router_after_debate(_base("debate")) == "reporter"

    def test_full_mode_goes_to_merge(self):
        assert _router_after_debate(_base("full")) == "merge"

    def test_standard_falls_to_reporter(self):
        # standard doesn't hit debate, but defensive
        assert _router_after_debate(_base("standard")) == "reporter"


# ── _router_after_merge ───────────────────────────────────────


class TestRouterAfterMerge:
    def test_social_enabled_goes_to_social(self):
        st = _base("full", run_social=True)
        assert _router_after_merge(st) == "social"

    def test_social_disabled_goes_to_reporter(self):
        st = _base("full", run_social=False)
        assert _router_after_merge(st) == "reporter"

    def test_missing_run_social_defaults_false(self):
        st = _base("full")
        assert _router_after_merge(st) == "reporter"

    def test_not_ok_social_true_goes_to_social(self):
        # run_social is checked before ok; node itself short-circuits
        st = _base("full", ok=False, run_social=True)
        assert _router_after_merge(st) == "social"
