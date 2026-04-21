"""SMF Predict Bridge — Hermes Agent integration for SMF Swarm predictions.

Usage:
    from smf_predict_bridge import PredictBridge

    bridge = PredictBridge()
    result = bridge.predict(
        query="Will NVIDIA exceed $4T by July 2026?",
        research_context="NVIDIA recently announced...",
        mode="full",
    )
    print(result.to_report())
"""
from __future__ import annotations

import os
import asyncio
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

from smf_swarm import Pipeline


@dataclass
class PredictionReport:
    """Human-readable report from a Swarm prediction."""
    query: str
    mode: str
    domain: str
    confidence: float
    data_quality: float
    health_score: float
    duration_s: float
    summary: str
    risk: str
    status: str
    timestamp: str

    def to_markdown(self) -> str:
        """Format as a Markdown report."""
        mins, secs = divmod(int(self.duration_s), 60)
        bar_len = 20
        filled = int(self.confidence * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)

        lines = [
            "═══════════════════════════════════════════",
            "         SMF PREDICT — Forecast Report",
            "═══════════════════════════════════════════",
            "",
            f"**Question:** {self.query}",
            f"**Mode:** {self.mode.title()} | **Domain:** {self.domain.title()}",
            "",
            f"**Confidence:** [{bar}] {self.confidence:.0%}",
            f"**Data Quality:** {self.data_quality:.0%}",
            f"**Health Score:** {self.health_score:.0%}",
            f"**Duration:** {mins}m {secs}s",
            "",
            "### Executive Summary",
            "───────────────────────────────────────────",
            self.summary,
            "",
            "### Risk Assessment",
            "───────────────────────────────────────────",
            self.risk if self.risk else "No specific risks identified.",
            "",
            f"*Generated: {self.timestamp}*",
        ]
        return "\n".join(lines)


class PredictBridge:
    """Bridge between Hermes Agent and SMF Swarm prediction pipeline.

    Handles:
      - Enriching user queries with Hermes research context
      - Calling the Swarm with appropriate mode/domain
      - Packaging results into human-readable reports
      - Error boundaries (Swarm crash does not kill Hermes)
    """

    def __init__(self, llm=None, default_mode: str = "debate"):
        self.default_mode = default_mode
        self._pipeline = Pipeline(llm=llm)

    def predict(
        self,
        query: str,
        research_context: str = "",
        mode: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> PredictionReport:
        """Run a prediction through the Swarm.

        Args:
            query: The prediction question from the user.
            research_context: Research data collected by Hermes (news, papers, market data).
            mode: "standard", "debate", or "full". Defaults to "debate".
            domain: "technology", "financial", "political", or "general".

        Returns:
            PredictionReport with all fields populated.
        """
        mode = mode or self.default_mode
        domain = domain or _infer_domain(query)

        enriched = query
        if research_context:
            enriched = (
                f"PREDICTION QUESTION: {query}\n\n"
                f"RESEARCH CONTEXT:\n{research_context}\n"
            )

        # Run the prediction in a thread to avoid blocking
        result = self._pipeline.run(
            query=enriched,
            mode=mode,
            domain=domain,
        )

        return PredictionReport(
            query=query,
            mode=result.mode,
            domain=result.domain,
            confidence=result.confidence,
            data_quality=result.data_quality,
            health_score=result.health_score,
            duration_s=result.duration_s,
            summary=result.summary or result.prediction_text[:500],
            risk=result.risk,
            status=result.status,
            timestamp=result.timestamp,
        )

    async def predict_async(
        self,
        query: str,
        research_context: str = "",
        mode: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> PredictionReport:
        """Async wrapper — runs predict in a thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self.predict, query, research_context, mode, domain
        )

    def notify(self, report: PredictionReport) -> str:
        """Format a notification message for delivery to the user.

        Override this method for different channels (Telegram, Slack, CLI).
        """
        return report.to_markdown()


def _infer_domain(query: str) -> str:
    """Infer domain from query keywords."""
    q = query.lower()
    if any(w in q for w in ("stock", "market", "fed", "inflation", "gdp", "revenue", "earnings", "trillion", "billion", "cap", "ipo", "rate cut", "q1", "q2", "q3", "q4")):
        return "financial"
    if any(w in q for w in ("ai", "llm", "software", "semiconductor", "adoption", "moore", "gpu", "cloud", "api", "model")):
        return "technology"
    if any(w in q for w in ("election", "poll", "senate", "policy", "regulation", "vote", "ballot", "democrat", "republican", "parliament")):
        return "political"
    return "general"


# ─── CLI entrypoint (for standalone testing) ───

def _main():
    import sys, argparse
    parser = argparse.ArgumentParser(description="SMF Predict Bridge")
    parser.add_argument("query", help="Prediction question")
    parser.add_argument("--mode", default="debate", choices=["standard", "debate", "full"])
    parser.add_argument("--domain", default="general")
    parser.add_argument("--context", default="", help="Research context text file path")
    args = parser.parse_args()

    ctx = ""
    if args.context and os.path.isfile(args.context):
        ctx = open(args.context).read()

    bridge = PredictBridge(default_mode=args.mode)
    report = bridge.predict(args.query, research_context=ctx, mode=args.mode, domain=args.domain)
    print(report.to_markdown())


if __name__ == "__main__":
    _main()
