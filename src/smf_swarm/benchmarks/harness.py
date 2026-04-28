"""SMF Swarm — BenchmarkHarness.

Runs SMF Swarm prediction pipeline against a canonical benchmark dataset,
records all predictions to BacktestStore, and produces calibrated
Brier/ECE/accuracy reports with reliability diagrams.

Usage:
    from smf_swarm.benchmarks.harness import BenchmarkHarness
    harness = BenchmarkHarness()
    report = harness.run(
        dataset=default_cache_dir() / "benchmarks" / "metaculus.jsonl",
        modes=["standard", "debate", "full"],
        multi_samples=[1, 5],
        output_dir="benchmark_results/",
        llm_model="gpt-4o-2024-08-06",
    )
    report.to_markdown("docs/benchmarks_results_metaculus.md")
"""

from __future__ import annotations

import json
import os
import time
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    _SKLEARN = True
except ImportError:
    _SKLEARN = False

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _MATPLOTLIB = True
except ImportError:
    _MATPLOTLIB = False

from smf_swarm import Pipeline
from smf_swarm.backtest import BacktestStore


@dataclass
class BenchmarkReport:
    """Container for a completed benchmark run."""

    benchmark_run_id: str
    dataset_name: str
    total_questions: int
    results: list[dict] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    plots_dir: str = ""
    duration_s: float = 0.0
    llm_model: str = ""
    hw_env_file: str = ""
    conformal_alpha: float | None = None
    conformal_cal_ratio: float = 0.7

    def to_json(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "benchmark_run_id": self.benchmark_run_id,
                    "dataset_name": self.dataset_name,
                    "total_questions": self.total_questions,
                    "llm_model": self.llm_model,
                    "duration_s": self.duration_s,
                    "metrics": self.metrics,
                    "plots_dir": self.plots_dir,
                    "conformal_alpha": self.conformal_alpha,
                    "conformal_cal_ratio": self.conformal_cal_ratio,
                },
                f,
                indent=2,
            )

    def to_markdown(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write("# Benchmark Results\n\n")
            f.write(f"**Dataset:** {self.dataset_name}\n\n")
            f.write(f"**Run ID:** `{self.benchmark_run_id}`\n\n")
            f.write(f"**LLM:** {self.llm_model}\n\n")
            f.write(f"**Questions:** {self.total_questions}\n\n")
            f.write(f"**Duration:** {self.duration_s:.1f}s\n\n")
            if self.conformal_alpha is not None:
                f.write(f"**Conformal α:** {self.conformal_alpha} | **Split:** {self.conformal_cal_ratio:.0%} cal / {1-self.conformal_cal_ratio:.0%} test\n\n")
            f.write("## Metrics\n\n")
            f.write("| Mode | Brier ↓ | ECE ↓ | MCE ↓ | Accuracy ↑ | Precision ↑ | Recall ↑ | F1 ↑ | Avg Dur(s) | CP Coverage | CP Width |\n")
            f.write("|------|---------|-------|-------|------------|-------------|----------|------|-----------|-------------|----------|\n")
            for mode, m in sorted(self.metrics.items()):
                brier = m.get("brier")
                ece = m.get("ece")
                mce = m.get("mce")
                acc = m.get("accuracy")
                prec = m.get("precision")
                rec = m.get("recall")
                f1 = m.get("f1")
                dur = m.get("avg_duration_s")
                row = f"| {mode} "
                row += f"| {brier:.4f} " if brier is not None else "| — "
                row += f"| {ece:.4f} " if ece is not None else "| — "
                row += f"| {mce:.4f} " if mce is not None else "| — "
                row += f"| {acc:.4f} " if acc is not None else "| — "
                row += f"| {prec:.4f} " if prec is not None else "| — "
                row += f"| {rec:.4f} " if rec is not None else "| — "
                row += f"| {f1:.4f} " if f1 is not None else "| — "
                row += f"| {dur:.1f} |\n" if dur is not None else "| — |\n"
                # Conformal columns
                if self.conformal_alpha is not None:
                    cp_cov = m.get("cp_empirical_coverage")
                    cp_wid = m.get("cp_mean_width")
                    row = row.rstrip("\n")
                    row += f"| {cp_cov:.4f} " if cp_cov is not None else "| — "
                    row += f"| {cp_wid:.4f} |\n" if cp_wid is not None else "| — |\n"
                f.write(row)
            if self.plots_dir:
                f.write(f"\n## Plots\n\nReliability diagrams: `{self.plots_dir}`\n")
            if self.conformal_alpha is not None:
                f.write(f"\n## Conformal Prediction\n\n")
                f.write(f"- **α (miscoverage):** {self.conformal_alpha}\n")
                f.write(f"- **Calibration split:** {self.conformal_cal_ratio:.0%}\n")
                # Find any mode with conformal metrics to print q̂
                for mode, m in sorted(self.metrics.items()):
                    if "cp_margin" in m:
                        f.write(f"- **Margin (q̂):** {m['cp_margin']}\n")
                        break
            f.write("\n---\nGenerated by SMF Swarm BenchmarkHarness\n")


class BenchmarkHarness:
    """Orchestrate benchmark runs and produce reports."""

    def __init__(self, llm_model: str = ""):
        self.llm_model = llm_model
        self.run_id = f"bench_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.store = BacktestStore()
        self.pipeline = Pipeline()

    def _load_dataset(self, path: str) -> list[dict]:
        """Load canonical JSONL dataset."""
        records = []
        with open(os.path.expanduser(path), "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                records.append(obj)
        return records

    def _brier(self, confidences: list[float], outcomes: list[int]) -> float:
        n = len(confidences)
        if n == 0:
            return 0.0
        return sum((c - o) ** 2 for c, o in zip(confidences, outcomes)) / n

    def _ece(self, confidences: list[float], outcomes: list[int], n_bins: int = 10) -> float:
        """Expected Calibration Error with equal-width bins."""
        n = len(confidences)
        if n == 0:
            return 0.0
        bins = np.linspace(0, 1, n_bins + 1)
        ece = 0.0
        for b in range(n_bins):
            lo, hi = bins[b], bins[b + 1]
            idx = [i for i, c in enumerate(confidences) if lo <= c < hi or (c == 1.0 and hi == 1.0)]
            if not idx:
                continue
            acc = sum(outcomes[i] for i in idx) / len(idx)
            avg_conf = sum(confidences[i] for i in idx) / len(idx)
            ece += len(idx) / n * abs(acc - avg_conf)
        return ece

    def _mce(self, confidences: list[float], outcomes: list[int], n_bins: int = 10) -> float:
        """Max Calibration Error."""
        n = len(confidences)
        if n == 0:
            return 0.0
        bins = np.linspace(0, 1, n_bins + 1)
        max_err = 0.0
        for b in range(n_bins):
            lo, hi = bins[b], bins[b + 1]
            idx = [i for i, c in enumerate(confidences) if lo <= c < hi or (c == 1.0 and hi == 1.0)]
            if not idx:
                continue
            acc = sum(outcomes[i] for i in idx) / len(idx)
            avg_conf = sum(confidences[i] for i in idx) / len(idx)
            max_err = max(max_err, abs(acc - avg_conf))
        return max_err

    def _classification_scores(self, confidences: list[float], outcomes: list[int], threshold: float = 0.5):
        predictions = [1 if c >= threshold else 0 for c in confidences]
        tp = sum(1 for p, o in zip(predictions, outcomes) if p == 1 and o == 1)
        fp = sum(1 for p, o in zip(predictions, outcomes) if p == 1 and o == 0)
        tn = sum(1 for p, o in zip(predictions, outcomes) if p == 0 and o == 0)
        fn = sum(1 for p, o in zip(predictions, outcomes) if p == 0 and o == 1)

        accuracy = (tp + tn) / len(outcomes) if outcomes else 0.0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        return accuracy, precision, recall, f1

    def _reliability_plot(self, confidences, outcomes, n_bins, out_path):
        if not _MATPLOTLIB:
            return
        bins = np.linspace(0, 1, n_bins + 1)
        bin_centers = []
        bin_accuracies = []
        bin_counts = []
        for b in range(n_bins):
            lo, hi = bins[b], bins[b + 1]
            idx = [i for i, c in enumerate(confidences) if lo <= c < hi or (c == 1.0 and hi == 1.0)]
            if not idx:
                continue
            bin_centers.append((lo + hi) / 2)
            bin_accuracies.append(sum(outcomes[i] for i in idx) / len(idx))
            bin_counts.append(len(idx))

        fig, ax = plt.subplots(figsize=(6, 5))
        ax.plot([0, 1], [0, 1], "k--", label="Perfect calibration")
        if bin_centers:
            ax.bar(bin_centers, bin_accuracies, width=0.08, alpha=0.6, edgecolor="black")
        ax.set_xlabel("Mean predicted confidence")
        ax.set_ylabel("Fraction of positives")
        ax.set_title("Reliability Diagram")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.legend(loc="upper left")
        fig.tight_layout()
        fig.savefig(out_path, dpi=150)
        plt.close(fig)

    def _naive_baseline(self, outcomes):
        n = len(outcomes)
        if n == 0:
            return 0.0, []
        confs = [0.5] * n
        return self._brier(confs, outcomes), confs

    def _base_rate_baseline(self, outcomes):
        n = len(outcomes)
        if n == 0:
            return 0.0, []
        rate = sum(outcomes) / n
        confs = [rate] * n
        return self._brier(confs, outcomes), confs

    def _logreg_baseline(self, texts, outcomes):
        if not _SKLEARN:
            warnings.warn("scikit-learn not installed; skipping LogReg TF-IDF baseline")
            return None, []
        if len(texts) < 10:
            warnings.warn("Not enough samples for LogReg TF-IDF baseline")
            return None, []
        vect = TfidfVectorizer(max_features=5000)
        X = vect.fit_transform(texts)
        clf = LogisticRegression(max_iter=1000)
        clf.fit(X, outcomes)
        preds = clf.predict_proba(X)[:, 1]
        brier = self._brier(list(preds), outcomes)
        return brier, list(preds)

    def run(
        self,
        dataset: str,
        modes: list[str] = None,
        multi_samples: list[int] = None,
        output_dir: str = "benchmark_results/",
        domain_map: dict = None,
        max_questions: int = 0,
        conformal_alpha: float | None = None,
        conformal_cal_ratio: float = 0.7,
    ) -> BenchmarkReport:
        """Run full benchmark suite.

        Args:
            dataset: Path to canonical JSONL file.
            modes: Pipeline modes to test (default ["standard", "debate", "full"]).
            multi_samples: List of multi_sample values (default [1]).
            output_dir: Where to write JSON + MD reports and plots.
            domain_map: Dict mapping source=>domain override, or None.
            max_questions: Cap number of questions (0 = all).
            conformal_alpha: If set, enable conformal prediction with miscoverage rate α.
                Calibrated intervals are reported alongside point predictions.
            conformal_cal_ratio: Fraction of data reserved for conformal calibration.
        Returns:
            BenchmarkReport with all metrics, plots, and optional conformal intervals.
        """
        t0 = time.time()
        modes = modes or ["standard", "debate", "full"]
        multi_samples = multi_samples or [1]
        domain_map = domain_map or {}

        out_dir = Path(os.path.expanduser(output_dir)) / self.run_id
        out_dir.mkdir(parents=True, exist_ok=True)
        plots_dir = out_dir / "plots"
        plots_dir.mkdir(exist_ok=True)

        records = self._load_dataset(dataset)
        if max_questions > 0:
            records = records[:max_questions]

        dataset_name = Path(dataset).stem
        print(f"Benchmark run: {self.run_id}")
        print(f"Dataset: {dataset_name} ({len(records)} questions)")
        print(f"Modes: {modes} | Multi-sample: {multi_samples}")
        if conformal_alpha is not None:
            cal_n = int(len(records) * conformal_cal_ratio)
            test_n = len(records) - cal_n
            print(f"Conformal: α={conformal_alpha} | cal={cal_n} | test={test_n}")
        print()

        all_results = []
        run_metrics = {}

        # Conformal split
        if conformal_alpha is not None:
            cal_n = int(len(records) * conformal_cal_ratio)
            cal_records = records[:cal_n]
            test_records = records[cal_n:]
        else:
            cal_records = []
            test_records = records

        # Baselines
        texts = [r["question_text"] for r in records]
        outcomes = [int(r["outcome"]) for r in records]

        # 1. Always 50%
        brier_50, _ = self._naive_baseline(outcomes)
        run_metrics["baseline_always_50"] = {"brier": brier_50}

        # 2. Base rate
        rate, _ = self._base_rate_baseline(outcomes)
        run_metrics["baseline_base_rate"] = {"brier": self._brier([rate] * len(outcomes), outcomes)}

        # 3. LogReg TF-IDF
        brier_lr, lr_confs = self._logreg_baseline(texts, outcomes)
        if brier_lr is not None:
            run_metrics["baseline_logreg"] = {"brier": brier_lr}

        # Conformal predictor (fitted on calibration runs)
        conformal_predictor = None
        if conformal_alpha is not None:
            cal_confidences = []
            print("Fitting conformal predictor on calibration split...")
            for i, rec in enumerate(cal_records, 1):
                if i % 10 == 0 or cal_n <= 20:
                    print(f"  [cal] [{i}/{cal_n}]")
                domain = domain_map.get(rec.get("source", ""), rec.get("domain", "general"))
                try:
                    result = self.pipeline.run(
                        query=rec["question_text"], mode="standard",
                        domain=domain, multi_sample=1,
                    )
                    cal_confidences.append(result.confidence)
                except Exception as e:
                    warnings.warn(f"Calibration run {i} failed: {e}")
                    cal_confidences.append(0.5)
            from smf_swarm.conformal import ConformalPredictor
            conformal_predictor = ConformalPredictor(alpha=conformal_alpha)
            cal_outcomes = [int(r["outcome"]) for r in cal_records]
            conformal_predictor.fit(cal_confidences, cal_outcomes)
            cp = conformal_predictor
            print(f"  q̂={cp.q_hat}, n_cal={cp.n_cal}")

        # SMF Swarm pipeline runs
        for mode in modes:
            for ms in multi_samples:
                label = f"swarm_{mode}_ms{ms}"
                print(f"\n━━━━━━━━ {label.upper()} ━━━━━━━━")
                confidences = []
                durations = []
                health_scores = []
                data_qualities = []
                social_mods = []
                conformal_intervals = []

                active_records = test_records if conformal_alpha is not None else records
                for i, rec in enumerate(active_records, 1):
                    if i % 10 == 0 or i == 1:
                        print(f"  [{i}/{len(active_records)}] {rec['question_text'][:60]}...")

                    domain = domain_map.get(rec.get("source", ""), rec.get("domain", "general"))
                    try:
                        result = self.pipeline.run(
                            query=rec["question_text"],
                            mode=mode,
                            domain=domain,
                            multi_sample=ms,
                        )
                        conf = result.confidence
                        pred_summary = result.summary
                    except Exception as e:
                        warnings.warn(f"Pipeline failed on question {i}: {e}")
                        conf = 0.5
                        pred_summary = ""

                    # Conformal interval
                    if conformal_predictor is not None:
                        ci = conformal_predictor.predict_interval(conf)
                        conformal_intervals.append(ci)

                    try:
                        self.store.record(
                            query=rec["question_text"],
                            domain=domain,
                            mode=f"{mode}_ms{ms}",
                            prediction=pred_summary,
                            confidence=conf,
                            llm_model=self.llm_model,
                            duration_s=result.duration_s if hasattr(result, "duration_s") else 0.0,
                            data_quality=result.data_quality if hasattr(result, "data_quality") else 0.5,
                            health_score=result.health_score if hasattr(result, "health_score") else 0.0,
                            social_modifier=result.social_modifier if hasattr(result, "social_modifier") else None,
                        )
                    except Exception as e:
                        warnings.warn(f"Backtest record failed: {e}")

                    confidences.append(conf)
                    if hasattr(result, "duration_s"):
                        durations.append(result.duration_s)
                    if hasattr(result, "health_score"):
                        health_scores.append(result.health_score)
                    if hasattr(result, "data_quality"):
                        data_qualities.append(result.data_quality)
                    if hasattr(result, "social_modifier") and result.social_modifier is not None:
                        social_mods.append(result.social_modifier)

                # Evaluate
                eval_outcomes = [int(r["outcome"]) for r in active_records]
                brier = self._brier(confidences, eval_outcomes)
                ece = self._ece(confidences, eval_outcomes)
                mce = self._mce(confidences, eval_outcomes)
                acc, prec, rec, f1 = self._classification_scores(confidences, eval_outcomes)

                run_metrics[label] = {
                    "brier": round(brier, 4),
                    "ece": round(ece, 4),
                    "mce": round(mce, 4),
                    "accuracy": round(acc, 4),
                    "precision": round(prec, 4),
                    "recall": round(rec, 4),
                    "f1": round(f1, 4),
                    "avg_duration_s": round(sum(durations) / len(durations), 1) if durations else 0.0,
                    "avg_health_score": round(sum(health_scores) / len(health_scores), 3) if health_scores else 0.0,
                    "avg_data_quality": round(sum(data_qualities) / len(data_qualities), 3) if data_qualities else 0.0,
                }

                # Conformal metrics
                if conformal_predictor and conformal_intervals:
                    cp = conformal_predictor
                    cp_score = cp.coverage_score(confidences, eval_outcomes)
                    run_metrics[label].update({
                        "cp_coverage_target": cp_score["target_coverage"],
                        "cp_empirical_coverage": cp_score["empirical_coverage"],
                        "cp_mean_width": cp_score["mean_width"],
                        "cp_margin": round(cp.q_hat, 4) if cp.q_hat else None,
                    })

                # Reliability plot
                plot_path = str(plots_dir / f"{label}_reliability.png")
                self._reliability_plot(confidences, eval_outcomes, 10, plot_path)
                print(f"  {label} — Brier: {brier:.4f} | ECE: {ece:.4f} | Acc: {acc:.4f}")
                if conformal_predictor:
                    print(f"    CP: coverage={run_metrics[label].get('cp_empirical_coverage')} "
                          f"target={cp_score['target_coverage']} "
                          f"width={cp_score['mean_width']:.4f}")

                all_results.append({
                    "mode": mode,
                    "multi_sample": ms,
                    "label": label,
                    "metrics": run_metrics[label],
                    "plot": plot_path,
                })

        t1 = time.time()
        report = BenchmarkReport(
            benchmark_run_id=self.run_id,
            dataset_name=dataset_name,
            total_questions=len(records),
            results=all_results,
            metrics=run_metrics,
            plots_dir=str(plots_dir),
            duration_s=round(t1 - t0, 1),
            llm_model=self.llm_model,
            conformal_alpha=conformal_alpha,
            conformal_cal_ratio=conformal_cal_ratio,
        )

        report.to_json(str(out_dir / "report.json"))
        report.to_markdown(str(out_dir / "report.md"))
        print(f"\nReport written to {out_dir}")
        return report
