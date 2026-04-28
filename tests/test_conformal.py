"""Tests for smf_swarm.conformal — ConformalPredictor and ConformalInterval.

Coverage goals
    • Interval math correctness (split conformal quantiles)
    • Empirical coverage ≥ target on synthetic cal/test splits
    • Edge cases: empty calibration, extreme α, tied scores
    • Adaptive binning fallback logic
    • Dataclass properties (width, is_certain, label)
"""

from __future__ import annotations

import math
import random

import numpy as np
import pytest

from smf_swarm.conformal import ConformalInterval, ConformalPredictor


# ── Fixtures ─────────────────────────────────────────────────

@pytest.fixture
def cp_05():
    """Fitted predictor with synthetic well-calibrated probabilities."""
    random.seed(42)
    np.random.seed(42)
    n = 500
    # Simulate *perfect* calibration:  c_i is the true prob(1) for each sample
    confidences = np.random.uniform(0.3, 0.9, size=n).tolist()
    outcomes = [1 if random.random() < c else 0 for c in confidences]
    cp = ConformalPredictor(alpha=0.05)
    cp.fit(confidences, outcomes)
    return cp


@pytest.fixture
def cp_10():
    random.seed(43)
    np.random.seed(43)
    n = 300
    confidences = np.random.uniform(0.1, 0.8, size=n).tolist()
    outcomes = [1 if random.random() < c else 0 for c in confidences]
    cp = ConformalPredictor(alpha=0.10)
    cp.fit(confidences, outcomes)
    return cp


# ── Dataclass behaviour ─────────────────────────────────────

def test_interval_properties():
    ci = ConformalInterval(
        low=0.55, high=0.85, margin=0.15, coverage_target=0.95, prediction_set=frozenset({1})
    )
    assert ci.width == pytest.approx(0.30, abs=1e-4)
    assert ci.is_certain is True
    assert ci.label == "yes"
    assert "yes" in repr(ci)


def test_interval_uncertain():
    ci = ConformalInterval(
        low=0.3, high=0.7, margin=0.20, coverage_target=0.90, prediction_set=frozenset({0, 1})
    )
    assert ci.width == pytest.approx(0.40, abs=1e-4)
    assert ci.is_certain is False
    assert ci.label == "uncertain"


def test_interval_no():
    ci = ConformalInterval(
        low=0.0, high=0.25, margin=0.25, coverage_target=0.95, prediction_set=frozenset({0})
    )
    assert ci.label == "no"


# ── Core prediction logic ───────────────────────────────────

def test_predict_interval_before_fit():
    cp = ConformalPredictor(alpha=0.05)
    with pytest.raises(RuntimeError, match="fit"):
        cp.predict_interval(0.72)


def test_predict_interval_yes(cp_05):
    ci = cp_05.predict_interval(0.95)
    assert 1 in ci.prediction_set
    assert ci.low >= 1.0 - ci.margin - 1e-9
    assert ci.coverage_target == 0.95


def test_predict_interval_no(cp_05):
    ci = cp_05.predict_interval(0.10)
    assert 0 in ci.prediction_set
    assert ci.high <= ci.margin


def test_predict_interval_uncertain(cp_05):
    ci = cp_05.predict_interval(0.50)
    if ci.prediction_set == frozenset({0, 1}):
        assert ci.low <= 0.50
        assert ci.high >= 0.50


def test_predict_intervals_batch(cp_05):
    confs = [0.1, 0.5, 0.9]
    intervals = cp_05.predict_intervals(confs)
    assert len(intervals) == 3
    for ci in intervals:
        assert ci.coverage_target == 0.95


# ── Calibration / quantile math ─────────────────────────────

def test_fit_empty_calibration():
    cp = ConformalPredictor(alpha=0.05)
    cp.fit([], [])
    assert cp.q_hat == 1.0
    assert cp.n_cal == 0


def test_fit_length_mismatch():
    cp = ConformalPredictor(alpha=0.05)
    with pytest.raises(ValueError, match="same length"):
        cp.fit([0.5], [0, 1])


def test_tied_scores():
    """All identical non-conformity scores — q̂ should handle gracefully."""
    cp = ConformalPredictor(alpha=0.05)
    confs = [0.5] * 20
    outs = [0] * 10 + [1] * 10
    cp.fit(confs, outs)
    assert cp.q_hat is not None
    ci = cp.predict_interval(0.5)
    assert 0 in ci.prediction_set
    assert 1 in ci.prediction_set


def test_extreme_alpha():
    cp = ConformalPredictor(alpha=0.01)
    confs = list(np.random.uniform(0.3, 0.9, size=100))
    outs = [1 if c > 0.5 else 0 for c in confs]
    cp.fit(confs, outs)
    ci = cp.predict_interval(0.6)
    assert ci.coverage_target == 0.99


def test_invalid_alpha():
    with pytest.raises(ValueError):
        ConformalPredictor(alpha=-0.1)
    with pytest.raises(ValueError):
        ConformalPredictor(alpha=1.0)
    with pytest.raises(ValueError):
        ConformalPredictor(alpha=1.5)


# ── Empirical coverage ────────────────────────────────────

def test_coverage_well_calibrated(cp_05):
    """On a fresh synthetic split, coverage must be ≥ target (most of the time).
    We run multiple seeds to avoid rare statistical flukes."""
    n_runs = 20
    coverages = []
    for _ in range(n_runs):
        confs = [float(x) for x in np.random.uniform(0.3, 0.9, size=200)]
        # Perfect-calibration oracle
        outs = [1 if random.random() < float(c) else 0 for c in confs]
        score = cp_05.coverage_score(confs, outs)
        coverages.append(score["empirical_coverage"])

    mean_coverage = sum(coverages) / len(coverages)
    # With correct conformal logic, mean empirical coverage should be ≥ target
    assert mean_coverage >= 0.94  # target 0.95, allow small MC variance


def test_coverage_90(cp_10):
    n_runs = 20
    coverages = []
    for _ in range(n_runs):
        confs = [float(x) for x in np.random.uniform(0.1, 0.8, size=200)]
        outs = [1 if random.random() < float(c) else 0 for c in confs]
        score = cp_10.coverage_score(confs, outs)
        coverages.append(score["empirical_coverage"])
    mean_coverage = sum(coverages) / len(coverages)
    assert mean_coverage >= 0.88  # target 0.90


def test_coverage_empty_test():
    cp = ConformalPredictor(alpha=0.05)
    cp.fit([0.6, 0.7, 0.8], [1, 1, 0])
    score = cp.coverage_score([], [])
    assert score["n"] == 0
    assert score["empirical_coverage"] == 0.0


# ── Adaptive binning ────────────────────────────────────────

def test_adaptive_binning_trivial():
    cp = ConformalPredictor(alpha=0.05)
    cp.fit([0.5] * 20, [0] * 10 + [1] * 10)
    confs = list(np.random.uniform(0, 1, size=30))
    outs = [1 if c > 0.5 else 0 for c in confs]
    bins = cp.adaptive_binning(confs, outs, n_bins=5)
    assert len(bins) == 5
    # Some bins are likely underpopulated; they should fall back to global q̂
    for b in range(5):
        assert "range" in bins[b]
        assert "q_hat" in bins[b]
        assert "n" in bins[b]


def test_adaptive_binning_underpopulated():
    cp = ConformalPredictor(alpha=0.05)
    cp.fit([0.5] * 20, [0] * 10 + [1] * 10)
    # Only 4 samples — every bin is underpopulated (< 5)
    confs = [0.1, 0.2, 0.3, 0.4]
    outs = [0, 0, 1, 1]
    bins = cp.adaptive_binning(confs, outs, n_bins=5)
    for b in range(5):
        assert bins[b]["q_hat"] == cp.q_hat
        assert "underpopulated" in bins[b].get("note", "")


def test_adaptive_binning_well_populated():
    cp = ConformalPredictor(alpha=0.05)
    confs = list(np.random.uniform(0.1, 0.9, size=50))
    outs = [1 if c > 0.5 else 0 for c in confs]
    cp.fit(confs, outs)
    bins = cp.adaptive_binning(confs, outs, n_bins=5)
    for b in range(5):
        assert bins[b]["q_hat"] is not None


# ── MAPIE wrapper (optional, only if installed) ───────────

MAPIE = pytest.importorskip("mapie.classification", reason="MAPIE not installed")


def test_mapie_import():
    """MAPIE import guard should raise cleanly."""
    cp = ConformalPredictor(alpha=0.05)
    # fit_mapie itself re-raises if MAPIE missing; here MAPIE exists.
    # We just verify the guard doesn't fire.
    assert not hasattr(cp, "_mapie_clf")


def test_mapie_fit_and_predict():
    from sklearn.linear_model import LogisticRegression

    cp = ConformalPredictor(alpha=0.10)
    n = 100
    X = [[float(x), float(y)] for x, y in zip(np.random.normal(size=n), np.random.normal(size=n))]
    y = [1 if x[0] + x[1] > 0 else 0 for x in X]
    cp.fit_mapie(X, y, estimator=LogisticRegression(max_iter=1000), method="score")
    intervals = cp.predict_mapie(X[:5])
    assert len(intervals) == 5
    for ci in intervals:
        assert ci.coverage_target == 0.90
        assert ci.prediction_set <= frozenset({0, 1})