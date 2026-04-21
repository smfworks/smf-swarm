"""SMF Swarm — Debate Engine.

3-agent adversarial ensemble: Optimist, Skeptic, Analyst.
Two rounds: opening statements + rebuttals.
Judge synthesizes consensus.

Usage:
    from smf_swarm.debate.engine import DebateEngine
    engine = DebateEngine(llm_client)
    result = engine.run(state)
    print(result['debate_confidence'], result['debate_consensus'])
"""

from __future__ import annotations

import re
from typing import TypedDict
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI


# ─── Prompts ────────────────────────────────────

OPTIMIST_PROMPT = (
    "You are a bold, knowledgeable industry optimist. You see the upside clearly. "
    "You know market dynamics, user adoption curves, and technology tipping points. "
    "You are NOT a cheerleader — you use data and precedent. "
    "Write a strongly argued opening or rebuttal. Be specific."
)

SKEPTIC_PROMPT = (
    "You are a rigorous, data-driven skeptic. You probe for hidden risks, "
    "overlooked failure modes, and incentive misalignments. "
    "You are NOT a pessimist — you are a professional stress-tester. "
    "Write a strongly argued opening or rebuttal. Be specific."
)

ANALYST_PROMPT = (
    "You are a balanced, evidence-weighted analyst. You synthesize both sides, "
    "identify what drives the outcome probabilistically, and assign confidence to each factor. "
    "You are NOT wishy-washy — you make point estimates. "
    "Write a strongly argued opening or rebuttal. Be specific."
)

JUDGE_PROMPT = (
    "You are a neutral judge with forecasting expertise. "
    "Given three positions and their rebuttals, synthesize the most robust, "
    "well-supported forecast. Acknowledge uncertainty, but commit to a probability. "
    "End with CONFIDENCE: [0-1]"
)


# ─── Engine ─────────────────────────────────────

class DebateEngine:
    """Runs the 3-agent debate ensemble."""

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    def run(self, state: dict) -> dict:
        """Execute full debate: openings, rebuttals, judge, dissent."""
        result = {}
        # Openings
        result.update(self._optimist_opening(state))
        result.update(self._skeptic_opening(state))
        result.update(self._analyst_opening(state))
        # Rebuttals
        result.update(self._optimist_rebuttal({**state, **result}))
        result.update(self._skeptic_rebuttal({**state, **result}))
        result.update(self._analyst_rebuttal({**state, **result}))
        # Judge + dissent
        result.update(self._judge({**state, **result}))
        result.update(self._dissent({**state, **result}))
        return result

    def _optimist_opening(self, state: dict) -> dict:
        resp = self.llm.invoke([HumanMessage(content=self._build_prompt(state, OPTIMIST_PROMPT, "opening"))])
        print("  [Debate] Optimist opening complete")
        return {"optimist_opening": resp.content}

    def _skeptic_opening(self, state: dict) -> dict:
        resp = self.llm.invoke([HumanMessage(content=self._build_prompt(state, SKEPTIC_PROMPT, "opening"))])
        print("  [Debate] Skeptic opening complete")
        return {"skeptic_opening": resp.content}

    def _analyst_opening(self, state: dict) -> dict:
        resp = self.llm.invoke([HumanMessage(content=self._build_prompt(state, ANALYST_PROMPT, "opening"))])
        print("  [Debate] Analyst opening complete")
        return {"analyst_opening": resp.content}

    def _optimist_rebuttal(self, state: dict) -> dict:
        resp = self.llm.invoke([HumanMessage(content=self._build_rebuttal(state, OPTIMIST_PROMPT, "optimist"))])
        return {"optimist_rebuttal": resp.content}

    def _skeptic_rebuttal(self, state: dict) -> dict:
        resp = self.llm.invoke([HumanMessage(content=self._build_rebuttal(state, SKEPTIC_PROMPT, "skeptic"))])
        return {"skeptic_rebuttal": resp.content}

    def _analyst_rebuttal(self, state: dict) -> dict:
        resp = self.llm.invoke([HumanMessage(content=self._build_rebuttal(state, ANALYST_PROMPT, "analyst"))])
        return {"analyst_rebuttal": resp.content}

    def _judge(self, state: dict) -> dict:
        o = state.get("optimist_opening", "")[:1200]
        s = state.get("skeptic_opening", "")[:1200]
        a = state.get("analyst_opening", "")[:1200]
        ro = state.get("optimist_rebuttal", "")[:600]
        rs = state.get("skeptic_rebuttal", "")[:600]
        ra = state.get("analyst_rebuttal", "")[:600]
        ctx = (
            f"{JUDGE_PROMPT}\n\n"
            f"QUERY: {state['query']}\n"
            f"OPTIMIST: {o}\n\n"
            f"SKEPTIC: {s}\n\n"
            f"ANALYST: {a}\n\n"
            f"REBUTTALS:\nO:{ro}\n\nS:{rs}\n\nA:{ra}\n\n"
            "Synthesize consensus. End with CONFIDENCE: [0-1]"
        )
        resp = self.llm.invoke([HumanMessage(content=ctx)])
        conf = self._extract_confidence(resp.content)
        print(f"  [Debate] Judge confidence: {conf:.2f}")
        return {"debate_consensus": resp.content, "debate_confidence": conf}

    def _dissent(self, state: dict) -> dict:
        ctx = f"From consensus: {state.get('debate_consensus', '')[:600]}\nExtract any MINORITY POSITION (under 100 words)."
        resp = self.llm.invoke([HumanMessage(content=ctx)])
        return {"dissent": resp.content}

    # ── Helpers ────────────────────────────────────

    def _build_prompt(self, state: dict, persona: str, round_type: str) -> str:
        return (
            f"{persona}\n\n"
            f"PREDICTION QUERY: {state['query']}\n"
            f"DOMAIN: {state['domain']}\n"
            f"FEATURES: {str(state.get('features', 'Not provided'))[:2000]}\n"
            f"DATA QUALITY: {state.get('data_quality', 0.5):.2f}\n\n"
            f"Present your {round_type} argument. Be specific and evidence-based."
        )

    def _build_rebuttal(self, state: dict, persona: str, my_role: str) -> str:
        roles = {
            "optimist": ["skeptic_opening", "analyst_opening"],
            "skeptic": ["optimist_opening", "analyst_opening"],
            "analyst": ["optimist_opening", "skeptic_opening"],
        }
        targets = roles[my_role]
        ctx = (
            f"{persona}\n\n"
            f"QUERY: {state['query']}\n\n"
            f"OPPOSING VIEW 1 ({targets[0]}):\n{state.get(targets[0], '')[:800]}\n\n"
            f"OPPOSING VIEW 2 ({targets[1]}):\n{state.get(targets[1], '')[:800]}\n\n"
            f"Write your rebuttal. Address weaknesses directly."
        )
        return ctx

    def _extract_confidence(self, text: str) -> float:
        text = text.replace("*", "")
        matches = re.findall(r'CONFIDENCE[:\\s]+([0-9]*\\.?[0-9]+)', text, re.I)
        if matches:
            return min(1.0, max(0.0, float(matches[-1])))
        return 0.5
