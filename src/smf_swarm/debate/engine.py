"""SMF Swarm — Debate Engine v1.1

3-agent adversarial ensemble: Optimist, Skeptic, Analyst.
Two rounds: opening statements + rebuttals.
Randomized-position judge synthesizes consensus via explicit
position-weighting to combat anchoring bias.
Equal text budgets for all three stances. Surfaced dissent.

Usage:
    from smf_swarm.debate.engine import DebateEngine
    engine = DebateEngine(llm_client)
    result = engine.run(state)
    print(result['debate_confidence'], result['debate_consensus'])
"""

from __future__ import annotations

import concurrent.futures
import random
import re
from typing import TypedDict
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI


# ─── Prompts ────────────────────────────────────

OPENING_BUDGET = 1500
REBUTTAL_BUDGET = 1000

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
    "You are a neutral judge with forecasting expertise."
)

JUDGE_WEIGHTING_INSTRUCTIONS = """
BEFORE assigning a final confidence, complete these steps IN ORDER:

1. SCORE each position independently (no reference to each other):
   - Evidence Quality: 1-10 (specific data, citations, precedents)
   - Logical Coherence: 1-10 (internal consistency, causal chain clarity)
   - Factual Grounding: 1-10 (base rates, known facts, falsifiable claims)

2. WEIGHT the positions by evidence quality:
   - Highest Evidence Quality receives the strongest weight
   - If two positions are tied, Logical Coherence breaks the tie
   - If still tied, Factual Grounding breaks the tie

3. SYNTHESIZE the most robust forecast by combining the highest-quality
   evidence from each position into a unified view.

4. Acknowledge the strongest COUNTER-ARGUMENT from the lowest-weighted
   position and explain why it does not overturn the consensus.

5. End with CONFIDENCE: [0-1]
"""


# ─── Typed state model ────────────────────────────

class _RoleCards(TypedDict):
    name: str
    prompt: str
    opening_key: str
    rebuttal_key: str


# ─── Engine ─────────────────────────────────────

class DebateEngine:
    """Runs the 3-agent debate ensemble with bias-mitigation."""

    # All roles with equal budgets — no structural advantage
    _ROLES: list[_RoleCards] = [
        {
            "name": "OPTIMIST",
            "prompt": OPTIMIST_PROMPT,
            "opening_key": "optimist_opening",
            "rebuttal_key": "optimist_rebuttal",
        },
        {
            "name": "SKEPTIC",
            "prompt": SKEPTIC_PROMPT,
            "opening_key": "skeptic_opening",
            "rebuttal_key": "skeptic_rebuttal",
        },
        {
            "name": "ANALYST",
            "prompt": ANALYST_PROMPT,
            "opening_key": "analyst_opening",
            "rebuttal_key": "analyst_rebuttal",
        },
    ]

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    def run(self, state: dict) -> dict:
        """Execute full debate with randomized ordering and surfaced dissent."""
        result: dict = {}

        # Phase 1: Openings (independent — run in parallel)
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self._opening, state, role): role["opening_key"]
                for role in self._ROLES
            }
            for future in concurrent.futures.as_completed(futures):
                result.update(future.result())

        # Phase 2: Rebuttals (sequential due to dependency on openings)
        for role in self._ROLES:
            result.update(self._rebuttal(state, role, result))

        # Phase 3: Judge (randomized presentation order)
        result.update(self._judge(state, result))

        # Phase 4: Dissent extraction
        result.update(self._dissent(state, result))

        return result

    # ── Openings ───────────────────────────────────

    def _opening(self, state: dict, role: _RoleCards) -> dict:
        ctx = self._build_prompt(state, role["prompt"], "opening")
        resp = self.llm.invoke([HumanMessage(content=ctx)])
        print(f"  [Debate] {role['name']} opening complete")
        return {role["opening_key"]: resp.content}

    # ── Rebuttals ──────────────────────────────────

    def _rebuttal(self, state: dict, role: _RoleCards, result: dict) -> dict:
        targets = self._get_opponents(role["name"])
        ctx = self._build_rebuttal(state, role, targets, result)
        resp = self.llm.invoke([HumanMessage(content=ctx)])
        print(f"  [Debate] {role['name']} rebuttal complete")
        return {role["rebuttal_key"]: resp.content}

    def _get_opponents(self, name: str) -> list[_RoleCards]:
        """Return the two roles that are NOT the given role."""
        return [r for r in self._ROLES if r["name"] != name]

    # ── Judge ───────────────────────────────────────

    def _judge(self, state: dict, result: dict) -> dict:
        # Randomize presentation order of the three positions
        shuffled_roles = list(self._ROLES)
        random.shuffle(shuffled_roles)

        # Build position blocks with equal budgets
        position_blocks: list[str] = []
        for role in shuffled_roles:
            o = result.get(role["opening_key"], "")[:OPENING_BUDGET]
            r = result.get(role["rebuttal_key"], "")[:REBUTTAL_BUDGET]
            position_blocks.append(
                f"{role['name']}:\n"
                f"{o}\n\n"
                f"REBUTTAL:\n{r}\n"
            )

        ctx = (
            f"{JUDGE_PROMPT}\n\n"
            f"PREDICTION QUERY: {state['query']}\n\n"
            f"{'=' * 60}\n"
            + f"\n{'=' * 60}\n".join(position_blocks)
            + f"\n{'=' * 60}\n\n"
            f"{JUDGE_WEIGHTING_INSTRUCTIONS}"
        )

        resp = self.llm.invoke([HumanMessage(content=ctx)])
        conf = self._extract_confidence(resp.content)
        print(f"  [Debate] Judge confidence: {conf:.2f}")
        return {"debate_consensus": resp.content, "debate_confidence": conf}

    # ── Dissent ────────────────────────────────────

    def _dissent(self, state: dict, result: dict) -> dict:
        """Extract the strongest counter-argument explicitly."""
        consensus = result.get("debate_consensus", "")[:OPENING_BUDGET]
        ctx = (
            f"Given this consensus:\n\n"
            f"{consensus}\n\n"
            f"Identify the SINGLE STRONGEST COUNTER-ARGUMENT that could overturn it. "
            f"Explain your reasoning in 50-100 words."
        )
        resp = self.llm.invoke([HumanMessage(content=ctx)])
        return {"dissent": resp.content}

    # ── Helpers ────────────────────────────────────

    def _build_prompt(self, state: dict, persona: str, round_type: str) -> str:
        return (
            f"{persona}\n\n"
            f"PREDICTION QUERY: {state['query']}\n"
            f"DOMAIN: {state['domain']}\n"
            f"FEATURES: {str(state.get('features', 'Not provided'))[:1800]}\n"
            f"DATA QUALITY: {state.get('data_quality', 0.5):.2f}\n\n"
            f"Present your {round_type} argument. Be specific and evidence-based.\n"
            f"Use data, precedents, and falsifiable claims when possible."
        )

    def _build_rebuttal(
        self, state: dict, role: _RoleCards, targets: list[_RoleCards], result: dict
    ) -> str:
        t1 = result.get(targets[0]["opening_key"], "")[:1200]
        t2 = result.get(targets[1]["opening_key"], "")[:1200]
        ctx = (
            f"{role['prompt']}\n\n"
            f"QUERY: {state['query']}\n\n"
            f"OPPOSING VIEW 1 ({targets[0]['name']}):\n{t1}\n\n"
            f"OPPOSING VIEW 2 ({targets[1]['name']}):\n{t2}\n\n"
            f"Write your rebuttal. Address weaknesses directly. "
            f"Use data to counter data, logic to counter logic."
        )
        return ctx

    def _extract_confidence(self, text: str) -> float:
        """Extract confidence from LLM output using last-match regex."""
        text = text.replace("*", "")
        matches = re.findall(r"CONFIDENCE[:\\s]+([0-9]*\\.?[0-9]+)", text, re.I)
        if matches:
            return min(1.0, max(0.0, float(matches[-1])))
        return 0.5
