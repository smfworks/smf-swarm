"""SMF Swarm — Backtesting layer: track predictions, ground truth, and calibration.

Stores every prediction run in a local SQLite database with enough metadata
to compute calibration curves, accuracy over time, and model drift.

Usage:
    from smf_swarm.backtest import BacktestStore
    bt = BacktestStore()
    bt.record(
        query="Will NVIDIA exceed $4T?",
        domain="financial",
        mode="full",
        prediction="Yes",
        confidence=0.78,
        llm_model="llama3.3",
    )
    # Later, when ground truth is known:
    bt.update_ground_truth(prediction_id, outcome=True)
    # Calibration report:
    bt.calibration_report(domain="financial")
"""

from __future__ import annotations

import json
import os
import sqlite3
import hashlib
from datetime import datetime
from typing import Optional, Sequence

from smf_swarm.platform_paths import default_data_dir


DEFAULT_DB = str(default_data_dir() / "backtest.db")


class BacktestStore:
    """SQLite-backed prediction history and calibration tracker."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DEFAULT_DB
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS predictions (
                    id TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    domain TEXT,
                    mode TEXT,
                    prediction TEXT,
                    confidence REAL,
                    ground_truth INTEGER,  -- NULL = unknown, -1 = false, 1 = true
                    llm_model TEXT,
                    temperature REAL,
                    social_agents INTEGER,
                    social_rounds INTEGER,
                    duration_s REAL,
                    data_quality REAL,
                    health_score REAL,
                    social_modifier REAL,
                    langgraph INTEGER,  -- 0 = classic, 1 = LangGraph
                    thread_id TEXT,
                    checkpoint_path TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );
                CREATE INDEX IF NOT EXISTS idx_pred_domain ON predictions(domain);
                CREATE INDEX IF NOT EXISTS idx_pred_mode ON predictions(mode);
                CREATE INDEX IF NOT EXISTS idx_pred_created ON predictions(created_at);
                CREATE INDEX IF NOT EXISTS idx_pred_thread ON predictions(thread_id);
            """)

    def record(
        self,
        query: str,
        domain: str,
        mode: str,
        prediction: str,
        confidence: float,
        llm_model: str = "",
        temperature: float = 0.3,
        social_agents: int = 15,
        social_rounds: int = 4,
        duration_s: float = 0.0,
        data_quality: float = 0.5,
        health_score: float = 0.0,
        social_modifier: Optional[float] = None,
        langgraph: bool = False,
        thread_id: str = "",
        checkpoint_path: str = "",
    ) -> str:
        """Record a new prediction. Returns prediction_id."""
        pred_id = hashlib.sha256(f"{query}{datetime.now().isoformat()}".encode()).hexdigest()[:16]
        data = {
            "id": pred_id,
            "query": query,
            "domain": domain,
            "mode": mode,
            "prediction": prediction[:1000] if prediction else "",
            "confidence": round(confidence, 4),
            "ground_truth": None,
            "llm_model": llm_model,
            "temperature": temperature,
            "social_agents": social_agents,
            "social_rounds": social_rounds,
            "duration_s": duration_s,
            "data_quality": data_quality,
            "health_score": health_score,
            "social_modifier": social_modifier,
            "langgraph": 1 if langgraph else 0,
            "thread_id": thread_id,
            "checkpoint_path": checkpoint_path,
        }
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO predictions
                (id, query, domain, mode, prediction, confidence, ground_truth,
                 llm_model, temperature, social_agents, social_rounds,
                 duration_s, data_quality, health_score, social_modifier,
                 langgraph, thread_id, checkpoint_path)
                VALUES
                (:id, :query, :domain, :mode, :prediction, :confidence, :ground_truth,
                 :llm_model, :temperature, :social_agents, :social_rounds,
                 :duration_s, :data_quality, :health_score, :social_modifier,
                 :langgraph, :thread_id, :checkpoint_path)
                """,
                data,
            )
            conn.commit()
        return pred_id

    def update_ground_truth(self, prediction_id: str, outcome: bool) -> bool:
        """Mark a prediction as resolved."""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.execute(
                "SELECT 1 FROM predictions WHERE id = ?",
                (prediction_id,),
            )
            if not c.fetchone():
                return False
            conn.execute(
                "UPDATE predictions SET ground_truth = ?, updated_at = datetime('now') WHERE id = ?",
                (1 if outcome else -1, prediction_id),
            )
            conn.commit()
        return True

    def search(self, domain: Optional[str] = None, mode: Optional[str] = None, limit: int = 50) -> list[dict]:
        """Search historical predictions."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            q = "SELECT * FROM predictions WHERE 1=1"
            params = []
            if domain:
                q += " AND domain = ?"
                params.append(domain)
            if mode:
                q += " AND mode = ?"
                params.append(mode)
            q += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(q, params).fetchall()
            return [dict(r) for r in rows]

    def calibration_report(self, domain: Optional[str] = None, mode: Optional[str] = None) -> dict:
        """Compute calibration metrics on resolved predictions.

        Returns:
            {
                "total": int,
                "resolved": int,
                "accuracy": float,       # fraction correct among resolved
                "brier_score": float,    # mean (confidence - outcome)²
                "calibration_bins": dict,  # {confidence_bin: (pct_correct, count)}
            }
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            q = "SELECT * FROM predictions WHERE ground_truth IS NOT NULL"
            params = []
            if domain:
                q += " AND domain = ?"
                params.append(domain)
            if mode:
                q += " AND mode = ?"
                params.append(mode)
            rows = conn.execute(q, params).fetchall()

        total = len(rows)
        if total == 0:
            return {
                "total": 0,
                "resolved": 0,
                "accuracy": None,
                "brier_score": None,
                "calibration_bins": {},
                "note": "No resolved predictions yet. Track ground truth over time.",
            }

        correct = 0
        squared_errors = 0.0
        bins = {}  # bucket: [count, correct_count]

        for r in rows:
            conf = r["confidence"] if r["confidence"] is not None else 0.5
            gt = 1 if r["ground_truth"] == 1 else 0
            pred_binary = 1 if conf >= 0.5 else 0
            if pred_binary == gt:
                correct += 1
            squared_errors += (conf - gt) ** 2

            bucket = round(conf, 1)  # 0.0, 0.1, ... 1.0
            if bucket not in bins:
                bins[bucket] = [0, 0]
            bins[bucket][0] += 1
            if pred_binary == gt:
                bins[bucket][1] += 1

        calibration_bins = {
            f"{b:.1f}": {
                "count": c,
                "accuracy": round(acc / c, 2) if c else 0,
            }
            for b, (c, acc) in bins.items()
        }

        return {
            "total": self.count(domain=domain, mode=mode),
            "resolved": total,
            "accuracy": round(correct / total, 4),
            "brier_score": round(squared_errors / total, 4),
            "calibration_bins": calibration_bins,
        }

    def count(self, domain: Optional[str] = None, mode: Optional[str] = None) -> int:
        with sqlite3.connect(self.db_path) as conn:
            q = "SELECT COUNT(*) FROM predictions WHERE 1=1"
            params = []
            if domain:
                q += " AND domain = ?"
                params.append(domain)
            if mode:
                q += " AND mode = ?"
                params.append(mode)
            return conn.execute(q, params).fetchone()[0]

    def delete_before(self, before: str) -> int:
        """Delete predictions older than ISO date string. Returns count deleted."""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.execute(
                "DELETE FROM predictions WHERE created_at < ?",
                (before,),
            )
            conn.commit()
            return c.rowcount
