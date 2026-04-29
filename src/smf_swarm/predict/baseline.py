"""SMF Swarm — Statistical baseline prediction (optional [predict] extras).

Provides hybrid baseline using Prophet, statsmodels, or scikit-learn when
time-series or tabular data can be extracted from the data-gathering node.
Runs alongside the LLM prediction and produces either a side-by-side
comparison or an ensemble.

Usage:
    from smf_swarm.predict.baseline import StatisticalBaseline
    bl = StatisticalBaseline()
    result = bl.forecast(query, raw_data=state["raw_data"])
    # result is a dict with "confidence", "prediction", "method"
"""

from __future__ import annotations

import json
import re
from typing import Optional

import numpy as np


class StatisticalBaseline:
    """Optional hybrid statistical forecaster."""

    def __init__(self):
        self._prophet = None
        self._statsmodels = None
        self._sklearn = None

    @property
    def prophet_available(self) -> bool:
        if self._prophet is None:
            try:
                from prophet import Prophet  # noqa: F401

                self._prophet = True
            except ImportError:
                self._prophet = False
        return self._prophet

    @property
    def statsmodels_available(self) -> bool:
        if self._statsmodels is None:
            try:
                import statsmodels.api as sm  # noqa: F401

                self._statsmodels = True
            except ImportError:
                self._statsmodels = False
        return self._statsmodels

    @property
    def sklearn_available(self) -> bool:
        if self._sklearn is None:
            try:
                import sklearn  # noqa: F401

                self._sklearn = True
            except ImportError:
                self._sklearn = False
        return self._sklearn

    def forecast(
        self, query: str, raw_data: str, features: Optional[str] = None
    ) -> dict:
        """Attempt a statistical forecast from raw text data.

        Returns a dict:
            {
                "method": str,
                "confidence": float | None,
                "prediction": str,
                "series_length": int | None,
                "error": str | None,
            }
        """
        # Try to extract a time series from raw_data
        series = self._extract_time_series(raw_data)
        if series is not None and len(series) >= 3:
            return self._run_time_series(series)

        # Try heuristic confidence from extracted counts
        heuristic = self._heuristic_from_features(raw_data, features)
        if heuristic is not None:
            return {
                "method": "heuristic",
                "confidence": heuristic,
                "prediction": f"(Heuristic) Directional confidence: {heuristic:.2f}",
                "series_length": None,
                "error": None,
            }

        return {
            "method": "none",
            "confidence": None,
            "prediction": "No statistical data available for this query.",
            "series_length": None,
            "error": "No time-series or extractable features found.",
        }

    def _extract_time_series(self, raw_data: str) -> Optional[list[tuple[str, float]]]:
        """Try to pull yyyy-mm-dd / value pairs from text or JSON snippets."""
        # Try to extract date: value pairs
        matches = re.findall(
            r"(\d{4}-\d{2}-\d{2})[\s:]?\s*([\d,.]+)",
            raw_data,
            re.IGNORECASE,
        )
        if len(matches) >= 3:
            return [(date, float(v.replace(",", ""))) for date, v in matches]

        # Try JSON-like arrays inside text
        json_search = re.search(r'(\{[^}]*"data"[^}]*\})', raw_data, re.DOTALL)
        if json_search:
            try:
                obj = json.loads(json_search.group(1))
                if isinstance(obj.get("data"), list) and len(obj["data"]) >= 3:
                    return [
                        (
                            str(item.get("date", i)),
                            float(item.get("value", item.get("v", 0))),
                        )
                        for i, item in enumerate(obj["data"])
                    ]
            except (json.JSONDecodeError, ValueError):
                pass

        return None

    def _run_time_series(self, series: list[tuple[str, float]]) -> dict:
        """Run the best available time-series model on the extracted series."""
        if self.prophet_available and len(series) >= 5:
            return self._run_prophet(series)
        if self.statsmodels_available and len(series) >= 8:
            return self._run_arima(series)
        if self.sklearn_available and len(series) >= 3:
            return self._run_trend(series)
        return {
            "method": "insufficient-data",
            "confidence": None,
            "prediction": "Collected time series too short for statistical model.",
            "series_length": len(series),
            "error": None,
        }

    def _run_prophet(self, series: list[tuple[str, float]]) -> dict:
        from prophet import Prophet

        import pandas as pd

        df = pd.DataFrame(series, columns=["ds", "y"])
        try:
            m = Prophet(yearly_seasonality=False, daily_seasonality=False)
            m.fit(df)
            future = m.make_future_dataframe(periods=1)
            forecast = m.predict(future)
            yhat = forecast["yhat"].iloc[-1]
            # Confidence estimated from model fit uncertainty
            ci_width = forecast["yhat_upper"].iloc[-1] - forecast["yhat_lower"].iloc[-1]
            conf = max(0.0, min(1.0, 1.0 - (ci_width / (2 * abs(yhat) + 1e-6))))
            return {
                "method": "prophet",
                "confidence": round(conf, 2),
                "prediction": f"Prophet forecast: {yhat:.2f}",
                "series_length": len(series),
                "error": None,
            }
        except Exception as e:
            return {
                "method": "prophet",
                "confidence": None,
                "prediction": "",
                "series_length": len(series),
                "error": str(e),
            }

    def _run_arima(self, series: list[tuple[str, float]]) -> dict:
        import statsmodels.api as sm

        try:
            values = [v for _, v in series]
            # Simple ARIMA(1,1,1)
            model = sm.tsa.ARIMA(values, order=(1, 1, 1))
            fit = model.fit()
            fc = fit.forecast(steps=1)[0]
            # Confidence from residual std
            resid_std = np.std(fit.resid)
            conf = max(0.0, min(1.0, 1.0 - (resid_std / (abs(np.mean(values)) + 1e-6))))
            return {
                "method": "arima",
                "confidence": round(conf, 2),
                "prediction": f"ARIMA(1,1,1) forecast: {fc:.2f}",
                "series_length": len(series),
                "error": None,
            }
        except Exception as e:
            return {
                "method": "arima",
                "confidence": None,
                "prediction": "",
                "series_length": len(series),
                "error": str(e),
            }

    def _run_trend(self, series: list[tuple[str, float]]) -> dict:
        """Linear trend with scikit-learn."""
        from sklearn.linear_model import LinearRegression
        from sklearn.preprocessing import PolynomialFeatures

        try:
            X = np.arange(len(series)).reshape(-1, 1)
            y = np.array([v for _, v in series])
            poly = PolynomialFeatures(degree=min(2, len(series) - 1))
            X_poly = poly.fit_transform(X)
            model = LinearRegression().fit(X_poly, y)
            pred = model.predict(poly.transform([[len(series)]]))[0]
            # Very rough confidence: R² proxy
            r2 = model.score(X_poly, y)
            conf = max(0.0, min(1.0, r2))
            return {
                "method": "trend",
                "confidence": round(conf, 2),
                "prediction": f"Linear trend forecast: {pred:.2f}",
                "series_length": len(series),
                "error": None,
            }
        except Exception as e:
            return {
                "method": "trend",
                "confidence": None,
                "prediction": "",
                "series_length": len(series),
                "error": str(e),
            }

    def _heuristic_from_features(
        self, raw_data: str, features: Optional[str] = None
    ) -> Optional[float]:
        """From raw text, count bullish/bearish keyword balance → a rough confidence proxy."""
        text = (raw_data + " " + (features or "")).lower()
        bullish = [
            "growth",
            "surge",
            "exceed",
            "accelerate",
            "bullish",
            "optimistic",
            "increase",
            "rise",
            "up",
            "gain",
        ]
        bearish = [
            "decline",
            "fall",
            "below",
            "risk",
            "bearish",
            "pessimistic",
            "decrease",
            "drop",
            "down",
            "loss",
        ]
        b = sum(1 for w in bullish if w in text)
        a = sum(1 for w in bearish if w in text)
        total = b + a
        if total == 0:
            return None
        return round(b / total, 2)
