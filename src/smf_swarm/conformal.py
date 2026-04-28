"""SMF Swarm — Conformal Prediction Module.

Provides calibrated uncertainty quantification for binary prediction confidence
scores. Uses split conformal prediction (Angelopoulos & Bates, 2023) to
guarantee marginal coverage:

    P( true outcome ∈ prediction_set ) ≥ 1 − α

The module is dependency-light — only requires `numpy`.  An optional `[conformal]`
extra installs `MAPIE` for advanced methods (cross-conformal, Jackknife+, …).

Usage
-----
    from smf_swarm.conformal import ConformalPredictor, ConformalInterval

    cp = ConformalPredictor(alpha=0.05)
    cp.fit(calibration_confidences, calibration_outcomes)
    interval = cp.predict_interval(confidence=0.72)
    # ConformalInterval(low=0.64, high=0.80, margin=0.08, ...)

    # Batch evaluation
    coverage = cp.coverage_score(test_confidences, test_outcomes)
    # {'empirical_coverage': 0.952, 'target_coverage': 0.95, ...}

    # Per-bin adaptive calibration
    bins = cp.adaptive_binning(confidences, outcomes, n_bins=10)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

try:
    import numpy as np
except ImportError:  # pragma: no cover
    raise ImportError("numpy is required for conformal prediction — install with: pip install numpy")


# ── Optional MAPIE soft dependency ─────────────────────────
# mapie ≥1.3 renamed MapieClassifier → SplitConformalClassifier,
# MapieRegressor → SplitConformalRegressor.  Try the new API first,
# then fall back to the legacy names.
_MAPIE_AVAILABLE = False  # type: ignore[assignment]
_MAPIE_CLASSIFIER: type | None = None
_MAPIE_REGRESSOR: type | None = None
try:
    from mapie.classification import MapieClassifier as _MAPIE_CLASSIFIER  # type: ignore[assignment]
    from mapie.regression import MapieRegressor as _MAPIE_REGRESSOR  # type: ignore[assignment]
    _MAPIE_AVAILABLE = True
except ImportError:
    pass
try:
    from mapie.classification import SplitConformalClassifier as _MAPIE_CLASSIFIER  # type: ignore[assignment]
    from mapie.regression import SplitConformalRegressor as _MAPIE_REGRESSOR  # type: ignore[assignment]
    _MAPIE_AVAILABLE = True
except ImportError:
    pass

# Backwards-compatible names for any code that still references them
MapieClassifier = _MAPIE_CLASSIFIER  # type: ignore[misc,assignment]
MapieRegressor = _MAPIE_REGRESSOR  # type: ignore[misc,assignment]


@dataclass(frozen=True)
class ConformalInterval:
    """Calibrated confidence interval for a binary prediction."""

    low: float          # lower bound on P(outcome=1)
    high: float         # upper bound on P(outcome=1)
    margin: float       # q̂ — the conformal threshold
    coverage_target: float  # 1 − α
    prediction_set: frozenset[int]  # {0}, {1}, or {0,1}

    @property
    def width(self) -> float:
        return round(self.high - self.low, 4)

    @property
    def is_certain(self) -> bool:
        """True iff the prediction set contains exactly one outcome."""
        return len(self.prediction_set) == 1

    @property
    def label(self) -> str:
        if self.prediction_set == frozenset({1}):
            return "yes"
        if self.prediction_set == frozenset({0}):
            return "no"
        return "uncertain"

    def __repr__(self) -> str:
        return (
            f"ConformalInterval(low={self.low}, high={self.high}, "
            f"margin={self.margin}, coverage={self.coverage_target}, "
            f"label='{self.label}')"
        )


class ConformalPredictor:
    """Split conformal prediction for binary classification confidence scores.

    Non-conformity scores are computed as the probability mass *not* assigned to
    the true class:  s_i = 1 − p̂_yᵢ .

    The calibration threshold q̂ is the ⌈(n+1)(1−α)/n⌉ quantile of the calibration
    non-conformity scores.

    Attributes:
        alpha: miscoverage rate (e.g. 0.05 → 95 % coverage).
        q_hat: fitted threshold; None until ``fit()`` is called.
        n_cal: number of calibration samples used for fitting.
    """

    def __init__(self, alpha: float = 0.05):
        if not 0 < alpha < 1:
            raise ValueError("alpha must be in (0, 1)")
        self.alpha = alpha
        self.q_hat: Optional[float] = None
        self.calibration_scores: list[float] = []
        self.n_cal: int = 0

    # ── Core API ─────────────────────────────────────────────

    def fit(self, confidences: list[float], outcomes: list[int]) -> "ConformalPredictor":
        """Fit on a calibration set.

        Args:
            confidences: Model confidence scores (probability of class 1).
            outcomes:    True binary outcomes (0 or 1).
        """
        if len(confidences) != len(outcomes):
            raise ValueError("confidences and outcomes must have the same length")
        if not confidences:
            self.q_hat = 1.0
            self.n_cal = 0
            return self

        # Non-conformity: s_i = 1 − p̂_yi
        scores = [
            1.0 - c if y == 1 else c
            for c, y in zip(confidences, outcomes)
        ]
        self.calibration_scores = scores
        self.n_cal = len(scores)

        # q̂ = ceil((n+1)(1−α)) / n  quantile
        q_level = math.ceil((self.n_cal + 1) * (1.0 - self.alpha)) / self.n_cal
        q_level = min(q_level, 1.0)
        self.q_hat = float(np.quantile(scores, q_level, method="higher"))
        return self

    def predict_interval(self, confidence: float) -> ConformalInterval:
        """Return a conformal interval for a single point prediction."""
        if self.q_hat is None:
            raise RuntimeError("Call fit() before predict_interval()")

        q = self.q_hat
        include_1 = confidence >= (1.0 - q)
        include_0 = confidence <= q
        pred_set: set[int] = set()
        if include_0:
            pred_set.add(0)
        if include_1:
            pred_set.add(1)

        # Interval construction
        if pred_set == {1}:
            low, high = max(0.0, 1.0 - q), 1.0
        elif pred_set == {0}:
            low, high = 0.0, min(1.0, q)
        else:
            # Ambiguous region — symmetric margin around confidence
            low = max(0.0, confidence - q)
            high = min(1.0, confidence + q)

        return ConformalInterval(
            low=round(low, 4),
            high=round(high, 4),
            margin=round(q, 4),
            coverage_target=round(1.0 - self.alpha, 4),
            prediction_set=frozenset(pred_set),
        )

    def predict_intervals(self, confidences: list[float]) -> list[ConformalInterval]:
        return [self.predict_interval(c) for c in confidences]

    # ── Validation ───────────────────────────────────────────

    def coverage_score(
        self, confidences: list[float], outcomes: list[int]
    ) -> dict:
        """Evaluate empirical marginal coverage on a held-out test set."""
        if len(confidences) != len(outcomes):
            raise ValueError("Length mismatch")
        n = len(confidences)
        if n == 0:
            return {
                "empirical_coverage": 0.0,
                "target_coverage": round(1.0 - self.alpha, 4),
                "mean_set_size": 0.0,
                "mean_width": 0.0,
                "n": 0,
            }

        covered = 0
        set_sizes = []
        widths = []
        for c, y in zip(confidences, outcomes):
            interval = self.predict_interval(c)
            if y in interval.prediction_set:
                covered += 1
            set_sizes.append(len(interval.prediction_set))
            widths.append(interval.width)

        return {
            "empirical_coverage": round(covered / n, 4),
            "target_coverage": round(1.0 - self.alpha, 4),
            "mean_set_size": round(sum(set_sizes) / n, 2),
            "mean_width": round(sum(widths) / n, 4),
            "n": n,
        }

    def adaptive_binning(
        self,
        confidences: list[float],
        outcomes: list[int],
        n_bins: int = 10,
    ) -> dict:
        """Conformalised adaptive binning.

        Fits a *local* q̂ in each confidence bin.  Bins with < 5 samples fall
        back to the global q̂.  Returns a dict mapping bin index → metadata.
        """
        if len(confidences) != len(outcomes):
            raise ValueError("Length mismatch")

        bins = np.linspace(0, 1, n_bins + 1)
        result: dict = {}

        for b in range(n_bins):
            lo, hi = bins[b], bins[b + 1]
            idx = [
                i
                for i, c in enumerate(confidences)
                if lo <= c < hi or (c == 1.0 and hi == 1.0)
            ]

            if len(idx) < 5:
                result[b] = {
                    "range": (round(float(lo), 3), round(float(hi), 3)),
                    "q_hat": self.q_hat,
                    "n": len(idx),
                    "note": "underpopulated — using global q̂",
                }
                continue

            local_confs = [confidences[i] for i in idx]
            local_outs = [outcomes[i] for i in idx]
            scores = [1.0 - c if y == 1 else c for c, y in zip(local_confs, local_outs)]
            n_local = len(scores)
            q_level = math.ceil((n_local + 1) * (1.0 - self.alpha)) / n_local
            q_level = min(q_level, 1.0)
            q_local = float(np.quantile(scores, q_level, method="higher"))

            result[b] = {
                "range": (round(float(lo), 3), round(float(hi), 3)),
                "q_hat": round(q_local, 4),
                "n": n_local,
            }

        return result

    # ── Optional MAPIE wrapper ─────────────────────────────────

    def fit_mapie(
        self,
        X_cal: list | np.ndarray,
        y_cal: list | np.ndarray,
        estimator=None,
        method: str = "score",
    ) -> "ConformalPredictor":
        """Fit using MAPIE (requires ``pip install smf-swarm[conformal]``).

        Args:
            X_cal: Feature matrix for calibration samples.
            y_cal: Binary labels.
            estimator: scikit-learn classifier (default LogisticRegression).
            method: ``score`` (split conformal) or ``cumulated_score``.
        """
        if not _MAPIE_AVAILABLE:
            raise ImportError(
                "MAPIE is not installed.  Install with: pip install smf-swarm[conformal]"
            )
        import sklearn.linear_model as lm

        if estimator is None:
            estimator = lm.LogisticRegression(max_iter=1000)

        if hasattr(X_cal, "tolist"):
            X_cal = X_cal.tolist()
        if hasattr(y_cal, "tolist"):
            y_cal = y_cal.tolist()

        est = estimator
        est.fit(X_cal, y_cal)

        cls = _MAPIE_CLASSIFIER
        if cls is None:
            raise RuntimeError("MAPIE classifier is not available")  # pragma: no cover

        # MAPIE 1.3+: renamed MapieClassifier → SplitConformalClassifier
        # and changed the constructor / calibration API.
        _is_v13 = cls.__name__ == "SplitConformalClassifier"
        if _is_v13:
            # mapie ≥1.3:  conformity_score replaces method; fit → conformalize when prefit=True
            score = "lac" if method == "score" else method
            self._mapie_clf = cls(
                estimator=est,
                confidence_level=round(1.0 - self.alpha, 4),
                conformity_score=score,
                prefit=True,
            )
            self._mapie_clf.conformalize(X_cal, y_cal)
        else:
            # legacy mapie <1.3
            self._mapie_clf = cls(estimator=est, method=method)
            self._mapie_clf.fit(X_cal, y_cal)
        return self

    def predict_mapie(
        self, X_new: list | np.ndarray, alpha: Optional[float] = None
    ) -> list[ConformalInterval]:
        """Predict using the fitted MAPIE classifier."""
        if not _MAPIE_AVAILABLE or not hasattr(self, "_mapie_clf"):
            raise RuntimeError("Call fit_mapie() before predict_mapie()")
        a = alpha if alpha is not None else self.alpha

        clf = self._mapie_clf
        _is_v13 = clf.__class__.__name__ == "SplitConformalClassifier"

        if _is_v13:
            # mapie ≥1.3: predict_set() returns (y_pred, y_ps) where y_ps may be (n, classes, 1)
            y_pred, y_ps = clf.predict_set(X_new)
            if y_ps.ndim == 3:
                y_ps = y_ps.squeeze(axis=-1)
        else:
            y_pred, y_ps = self._mapie_clf.predict(X_new, alpha=a)

        intervals = []
        for pred, ps in zip(y_pred, y_ps):
            # ps shape: (n_classes,) bool array
            set_bits = {int(i) for i, included in enumerate(ps) if bool(included)}
            q_hat = self.q_hat if self.q_hat is not None else self.alpha
            low = 0.0 if 0 in set_bits else max(0.0, 1.0 - q_hat)
            high = 1.0 if 1 in set_bits else min(1.0, q_hat)
            intervals.append(
                ConformalInterval(
                    low=round(low, 4),
                    high=round(high, 4),
                    margin=round(q_hat, 4),
                    coverage_target=round(1.0 - self.alpha, 4),
                    prediction_set=frozenset(set_bits),
                )
            )
        return intervals


# ── Convenience exports ──────────────────────────────────────

__all__ = [
    "ConformalPredictor",
    "ConformalInterval",
]