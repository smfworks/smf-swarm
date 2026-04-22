"""SMF Swarm CLI — smf-swarm.

Entry point for the terminal. Provides:
  configure   — first-time wizard
  predict     — run a prediction
  test        — connectivity smoke test
  version     — show version
  config      — show current configuration

Usage:
    smf-swarm configure
    smf-swarm predict "Will X happen?" --mode debate
"""

from __future__ import annotations

import sys
import argparse
from pathlib import Path


def main(argv: list[str] = None):
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="smf-swarm",
        description="SMF Swarm — Predictive analysis with agent swarms",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  smf-swarm configure                    # First-time setup wizard
  smf-swarm predict "Will NVIDIA exceed $4T?" --mode full --domain financial
  smf-swarm test                         # Verify LLM connection
  smf-swarm version                      # Show installed version
  smf-swarm config                       # Show current configuration
""",
    )
    sub = parser.add_subparsers(dest="cmd", help="Command to run")

    # ── configure ────────────────────────────────
    sub.add_parser("configure", help="Run first-time configuration wizard")

    # ── predict ──────────────────────────────────
    p_predict = sub.add_parser("predict", help="Run a prediction")
    p_predict.add_argument("query", help="The prediction question")
    p_predict.add_argument("--mode", default=None, choices=["standard", "debate", "full"],
                           help="Prediction mode (default: from config)")
    p_predict.add_argument("--domain", default=None, help="Domain: technology|financial|political|general")
    p_predict.add_argument("--no-social", dest="social", action="store_false",
                           default=True, help="Disable social simulation even in full mode")
    p_predict.add_argument("--output", "-o", default=None, help="Output file path (JSON)")

    # ── test ─────────────────────────────────────
    sub.add_parser("test", help="Run a connectivity smoke test against your LLM")

    # ── version ──────────────────────────────────
    sub.add_parser("version", help="Show version")

    # ── config ───────────────────────────────────
    sub.add_parser("config", help="Show current configuration")

    # ── web ───────────────────────────────────────
    p_web = sub.add_parser("web", help="Launch the web UI server")
    p_web.add_argument("--port", type=int, default=8080, help="Port to bind (default: 8080)")
    p_web.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")

    args = parser.parse_args(argv)
    if not args.cmd:
        parser.print_help()
        sys.exit(0)

    # Dispatch
    if args.cmd == "configure":
        _cmd_configure()
    elif args.cmd == "predict":
        _cmd_predict(args)
    elif args.cmd == "test":
        _cmd_test()
    elif args.cmd == "version":
        _cmd_version()
    elif args.cmd == "config":
        _cmd_config()
    elif args.cmd == "web":
        _cmd_web(args)


def _cmd_configure():
    from smf_swarm.config import configure
    configure()


def _cmd_predict(args):
    from smf_swarm.pipeline import Pipeline
    from smf_swarm.config import get_config
    import json
    from datetime import datetime

    cfg = get_config()
    mode = args.mode or cfg.default_mode
    domain = args.domain or cfg.default_domain
    run_social = args.social

    print(f"\n{'='*60}")
    print(f"  SMF Swarm — Prediction Mode: {mode.upper()}")
    print(f"  Query: {args.query}")
    print(f"  Domain: {domain}")
    if run_social:
        print(f"  Social simulation: ENABLED ({cfg.social_agents} agents × {cfg.social_rounds} rounds)")
    print(f"{'='*60}\n")

    pipeline = Pipeline()
    result = pipeline.run(
        query=args.query,
        mode=mode,
        domain=domain,
        run_social=run_social,
    )

    print(f"\n{'='*60}")
    print(f"  RESULT")
    print(f"{'='*60}")
    print(f"  Confidence:      {result.confidence:.2f}")
    print(f"  Data Quality:    {result.data_quality:.2f}")
    print(f"  Health Score:    {result.health_score:.2f}")
    print(f"  Duration:        {result.duration_s:.0f}s")
    if result.social_modifier is not None:
        print(f"  Social Modifier: {result.social_modifier:+.2f}")
    print(f"\n  EXECUTIVE SUMMARY")
    print(f"  {'-'*56}")
    for line in result.summary.split("\n")[:10]:
        print(f"  {line}")
    print(f"\n{'='*60}")

    if args.output:
        out = {
            "query": result.query,
            "mode": result.mode,
            "confidence": result.confidence,
            "data_quality": result.data_quality,
            "health_score": result.health_score,
            "duration_s": result.duration_s,
            "summary": result.summary,
            "risk": result.risk,
            "social_modifier": result.social_modifier,
            "timestamp": datetime.now().isoformat(),
        }
        Path(args.output).write_text(json.dumps(out, indent=2))
        print(f"\n  Saved to: {args.output}")


def _cmd_test():
    from smf_swarm.config import load_config, create_llm
    from langchain_core.messages import HumanMessage

    cfg = load_config()
    print("  Testing connection...")
    try:
        llm = create_llm(cfg.llm)
        resp = llm.invoke([HumanMessage(content="Answer: what is 2+2? (one word)")])
        print(f"  ✅ Connection OK — model: {cfg.llm.model}")
        print(f"     Response: {resp.content[:100]}")
    except Exception as e:
        print(f"  ❌ Connection FAILED: {e}")
        print(f"\n  Troubleshooting:")
        print(f"    1. Is your LLM server running? (e.g., 'ollama serve')")
        print(f"    2. Is base_url correct? Current: {cfg.llm.base_url}")
        print(f"    3. Run 'smf-swarm configure' to fix settings")
        sys.exit(1)


def _cmd_version():
    from smf_swarm import __version__, __author__, __contact__
    print(f"smf-swarm {__version__}")
    print(f"Author:    {__author__}")
    print(f"Contact:   {__contact__}")


def _cmd_config():
    from smf_swarm.config import load_config, DEFAULT_CONFIG_FILE
    import json
    cfg = load_config()
    print(f"\nConfig file: {DEFAULT_CONFIG_FILE}")
    print(f"{'='*60}")
    print(json.dumps(cfg.__dict__, indent=2, default=str))


def _cmd_web(args):
    from smf_swarm.web.app import run_server
    run_server(host=args.host, port=args.port)
