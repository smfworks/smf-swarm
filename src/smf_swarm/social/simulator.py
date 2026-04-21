"""SMF Swarm — MiroFish-Style Social Simulator.

Agent swarm that debates a prediction topic and generates:
  - Sentiment trajectory across rounds
  - Confidence modifier (swarm-level calibration signal)
  - Knowledge graph of agent interactions
  - Qualitative social report

Usage:
    from smf_swarm.social.simulator import SocialSimulator
    sim = SocialSimulator(llm)
    result = sim.run("Will X happen?", domain="tech", agent_count=15, rounds=4)
"""

from __future__ import annotations

import os, re, random, uuid
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime
from langchain_core.messages import HumanMessage


@dataclass
class Persona:
    id: str
    name: str
    role: str
    organization: str
    stance: str          # optimist | skeptic | neutral
    influence: float     # 0–3
    activity: float      # 0–1
    expertise: str
    background: str = ""

    def to_prompt(self) -> str:
        return (f"{self.name} ({self.role} at {self.organization}) — "
                f"stance: {self.stance}, influence: {self.influence:.1f}, "
                f"expertise: {self.expertise}")


@dataclass
class SocialAction:
    round: int
    persona_id: str
    persona_name: str
    action_type: str   # post | react | endorse | challenge
    content: str
    target_id: str = ""
    sentiment: float = 0.0


class InMemoryGraph:
    """Lightweight knowledge graph for simulation."""
    def __init__(self):
        self.nodes: list[dict] = []
        self.edges: list[dict] = []
    def add_node(self, label: str, props: dict) -> str:
        nid = str(uuid.uuid4())[:8]
        self.nodes.append({"id": nid, "label": label, **props})
        return nid
    def add_edge(self, source: str, target: str, relation: str, props: dict = None):
        self.edges.append({"source": source, "target": target, "relation": relation, "props": props or {}})
    def extract_knowledge(self, text: str):
        # Simple keyword extraction for demo; production: use NER/LLM extraction
        entities = re.findall(r'([A-Z][a-zA-Z ]{3,30})', text)
        for ent in set(entities):
            if len(ent.strip()) > 4:
                self.add_node("Entity", {"name": ent.strip()})


class SocialSimulator:
    def __init__(self, llm):
        self.llm = llm

    def run(self, query: str, domain: str = "general", agent_count: int = 15, rounds: int = 4) -> dict:
        print(f"  [SocialSim] Spawning {agent_count} agents × {rounds} rounds...")
        personas = self._generate_personas(domain, agent_count)
        simulator = _Simulator(query, domain, personas, rounds, self.llm)
        return simulator.run()

    def _generate_personas(self, domain: str, count: int) -> list[Persona]:
        templates = self._get_templates(domain)
        personas = []
        for i in range(count):
            t = templates[i % len(templates)]
            personas.append(Persona(
                id=f"agent_{i}",
                name=t[0],
                role=t[1],
                organization=t[2],
                stance=t[3],
                influence=t[4],
                activity=t[5],
                expertise=t[6],
            ))
        return personas

    def _get_templates(self, domain: str) -> list[tuple]:
        return {
            "technology": [
                ("Alex Mercer", "VC", "Andreessen Horowitz", "optimist", 2.5, 0.7, "AI startups, enterprise adoption"),
                ("Sarah Chen", "PM", "BlackRock", "neutral", 2.0, 0.6, "tech valuations, ETF flows"),
                ("Dr. Yuki Tanaka", "Researcher", "MIT AI Lab", "skeptic", 2.8, 0.5, "AI safety, model reliability"),
                ("James Wright", "Analyst", "Goldman Sachs", "skeptic", 2.2, 0.7, "risk management, financial AI"),
                ("Priya Patel", "Regulator", "SEC", "skeptic", 3.0, 0.4, "AI compliance, market manipulation"),
                ("Mike Torres", "Founder", "NeuralDash", "optimist", 1.5, 0.9, "AI agents, automation"),
            ],
            "political": [
                ("Elena Rossi", "Pollster", "FiveThirtyEight", "neutral", 2.5, 0.6, "electoral modeling, polling accuracy"),
                ("Tom Harris", "Strategist", "GOP Analytics", "skeptic", 2.3, 0.7, "swing-state demographics, turnout"),
                ("Amara Johnson", "Activist", "MoveOn", "optimist", 2.0, 0.6, "grassroots mobilization, voter registration"),
                ("Dr. Klaus Weber", "Political Scientist", "Humboldt University", "skeptic", 2.8, 0.5, "comparative politics, ideology"),
            ],
            "financial": [
                ("Sarah Chen", "CFO", "TechVenture Capital", "optimist", 2.5, 0.7, "venture capital, tech valuation"),
                ("James Wright", "Risk Analyst", "Goldman Sachs", "skeptic", 2.0, 0.8, "risk management, derivatives"),
                ("Dr. Priya Patel", "Economic Researcher", "Brookings Institute", "neutral", 2.8, 0.5, "macroeconomics, policy"),
                ("Mike Torres", "Portfolio Manager", "BlackRock", "optimist", 2.2, 0.6, "asset management, ETFs"),
                ("Linda Zhang", "Regulator", "SEC", "skeptic", 3.0, 0.4, "securities regulation, compliance"),
            ],
        }.get(domain, [
            ("Alice Generic", "Analyst", "SMF Works", "neutral", 2.0, 0.6, "general analysis"),
            ("Bob Pessimist", "Risk Manager", "SMF Works", "skeptic", 2.0, 0.6, "risk assessment"),
            ("Carla Optimist", "Strategist", "SMF Works", "optimist", 2.0, 0.6, "strategic planning"),
        ])


# ─── Internal simulator ─────────────────────────

class _Simulator:
    def __init__(self, query: str, domain: str, personas: list[Persona], rounds: int, llm):
        self.query = query
        self.domain = domain
        self.personas = personas
        self.rounds = rounds
        self.llm = llm
        self.actions: list[SocialAction] = []
        self.graph = InMemoryGraph()
        self.round_summaries: list[str] = []

    def run(self) -> dict:
        self._seed_graph()
        for rn in range(1, self.rounds + 1):
            acts = self._run_round(rn)
            self.actions.extend(acts)
            summary = self._summarize_round(rn, acts)
            self.round_summaries.append(summary)
            for a in acts:
                self.graph.extract_knowledge(a.content[:300])
        return self._generate_report()

    def _seed_graph(self):
        self.graph.add_node("Query", {"text": self.query, "domain": self.domain})
        for p in self.personas:
            self.graph.add_node("Persona", {"name": p.name, "role": p.role, "stance": p.stance})

    def _run_round(self, round_num: int) -> list[SocialAction]:
        actions = []
        ctx = self._build_context(round_num)
        for p in self.personas:
            if random.random() > p.activity:
                continue
            action = self._generate_action(p, round_num, ctx)
            if action:
                actions.append(action)
        return actions

    def _build_context(self, round_num: int) -> str:
        if round_num == 1:
            return f"Topic: {self.query}\nDomain: {self.domain}\nFirst round. No prior discussion."
        recent = self.actions[-20:]
        lines = [f"Topic: {self.query}", f"Domain: {self.domain}"]
        lines.append(f"\nRecent discussion (Round {round_num-1}):")
        for a in recent:
            lines.append(f"  {a.persona_name}: {a.content[:150]}")
        return "\n".join(lines)

    def _generate_action(self, persona: Persona, round_num: int, context: str) -> Optional[SocialAction]:
        action_types = ["post", "react", "endorse", "challenge"]
        weights = {
            "optimist": [0.4, 0.2, 0.3, 0.1],
            "skeptic": [0.3, 0.2, 0.1, 0.4],
            "neutral": [0.3, 0.3, 0.2, 0.2],
        }[persona.stance]
        action_type = random.choices(action_types, weights=weights, k=1)[0]

        target_id = ""
        if action_type in ("react", "endorse", "challenge") and self.actions:
            target = random.choice(self.actions[-10:])
            target_id = target.persona_id

        prompt = (
            f"You are {persona.to_prompt()}.\n\n"
            f"{context}\n\n"
            f"This is round {round_num}. You are {action_type}ing on the topic.\n"
            f"Stay in character. Be specific — reference data, trends, or experience.\n"
            f"Write a concise {action_type} (2–4 sentences). Be direct and opinionated."
        )
        resp = self.llm.invoke([HumanMessage(content=prompt)])

        sentiment = self._estimate_sentiment(resp.content, persona.stance)

        return SocialAction(
            round=round_num,
            persona_id=persona.id,
            persona_name=persona.name,
            action_type=action_type,
            content=resp.content,
            target_id=target_id,
            sentiment=sentiment,
        )

    def _estimate_sentiment(self, text: str, stance: str) -> float:
        text = text.lower()
        bullish = ["likely", "yes", "growth", "surge", "exceed", "accelerate", "bullish", "optimistic"]
        bearish = ["unlikely", "no", "decline", "fall", "below", "risk", "bearish", "pessimistic"]
        b = sum(1 for w in bullish if w in text)
        c = sum(1 for w in bearish if w in text)
        if stance == "optimist":
            c = max(0, c - 1)  # optimists use bearish words more cautiously
        elif stance == "skeptic":
            b = max(0, b - 1)
        if b + c == 0:
            return 0.0
        return round((b - c) / max(b + c, 1), 2)

    def _summarize_round(self, round_num: int, actions: list[SocialAction]) -> str:
        total = len(actions)
        avg_sent = sum(a.sentiment for a in actions) / total if total else 0
        return f"Round {round_num}: {total} actions, avg_sentiment: {avg_sent:+.2f}"

    def _generate_report(self) -> dict:
        # Sentiment trajectory
        trajectory = []
        for rn in range(1, self.rounds + 1):
            round_actions = [a for a in self.actions if a.round == rn]
            if round_actions:
                avg = sum(a.sentiment for a in round_actions) / len(round_actions)
                trajectory.append((rn, round(avg, 2)))

        # Confidence modifier based on sentiment trajectory
        if trajectory:
            start_sent = trajectory[0][1]
            end_sent = trajectory[-1][1]
            modifier = round(end_sent - start_sent, 2)  # + means optimism grew
        else:
            modifier = 0.0

        # Build qualitative report
        top_posts = sorted(self.actions, key=lambda a: a.sentiment, reverse=True)[:3]
        bot_posts = sorted(self.actions, key=lambda a: a.sentiment)[:3]
        report = (
            f"Social Simulation Report ({self.rounds} rounds, {len(self.actions)} total actions)\n\n"
            f"Sentiment trajectory: {trajectory}\n"
            f"Confidence modifier: {modifier:+.2f}\n\n"
            f"Most bullish actions:\n"
            + "\n".join(f"  • {a.persona_name}: {a.content[:120]}" for a in top_posts)
            + "\n\nMost bearish actions:\n"
            + "\n".join(f"  • {a.persona_name}: {a.content[:120]}" for a in bot_posts)
        )

        return {
            "social_report": report,
            "confidence_modifier": modifier,
            "sentiment_trajectory": trajectory,
            "total_actions": len(self.actions),
            "agent_count": len(self.personas),
        }
