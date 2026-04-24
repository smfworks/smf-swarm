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
  smf-swarm profile                      # Detect hardware & choose profile
  smf-swarm profile --auto               # Auto-apply recommended profile
  smf-swarm predict "Will NVIDIA exceed $4T?" --mode full --domain financial
  smf-swarm test                         # Verify LLM connection
  smf-swarm version                      # Show installed version
  smf-swarm config                       # Show current configuration
""",
    )
    sub = parser.add_subparsers(dest="cmd", help="Command to run")

    # ── configure ────────────────────────────────
    sub.add_parser("configure", help="Run first-time configuration wizard")

    # ── profile ──────────────────────────────────
    p_profile = sub.add_parser("profile", help="Detect hardware and choose swarm profile")
    p_profile.add_argument("--auto", dest="auto", action="store_true",
                           default=False, help="Auto-apply recommended profile (non-interactive)")
    p_profile.add_argument("--show", dest="show", action="store_true",
                           default=False, help="Show current profile without changing")
    p_profile.add_argument("--reset", dest="reset", action="store_true",
                           default=False, help="Force re-detection on next run")

    # ── predict ──────────────────────────────────
    p_predict = sub.add_parser("predict", help="Run a prediction")
    p_predict.add_argument("query", help="The prediction question")
    p_predict.add_argument("--mode", default=None, choices=["standard", "debate", "full"],
                           help="Prediction mode (default: from config)")
    p_predict.add_argument("--domain", default=None, help="Domain: technology|financial|political|general")
    p_predict.add_argument("--no-social", dest="social", action="store_false",
                           default=True, help="Disable social simulation even in full mode")
    p_predict.add_argument("--multi-sample", type=int, default=1, dest="multi_sample",
                           help="Number of temperature-swept runs for confidence uncertainty (default: 1)")
    p_predict.add_argument("--output", "-o", default=None, help="Output file path (JSON)")
    p_predict.add_argument("--no-cache", dest="no_cache", action="store_true",
                           default=False, help="Bypass LLM response cache")

    # ── backtest ─────────────────────────────────
    p_backtest = sub.add_parser("backtest", help="Report calibration and historical accuracy")
    p_backtest.add_argument("--domain", default=None, help="Filter by domain")
    p_backtest.add_argument("--mode", default=None, choices=["standard", "debate", "full"],
                           help="Filter by mode")
    p_backtest.add_argument("--set-truth", dest="truth_id", default=None,
                           help="Update ground truth for a prediction ID")
    p_backtest.add_argument("--outcome", dest="outcome", default=None,
                           choices=["true", "false"],
                           help="Outcome for --set-truth (true/false)")

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
    p_web.add_argument("--token", type=str, default=None, help="Optional bearer token for API auth")
    p_web.add_argument("--rate-limit", dest="rate_limit", type=int, nargs=2, metavar=("COUNT", "SECONDS"),
                       default=None, help="Rate limit API requests per IP (e.g. --rate-limit 10 60)")

    args = parser.parse_args(argv)
    if not args.cmd:
        parser.print_help()
        sys.exit(0)

    # Dispatch
    if args.cmd == "configure":
        _cmd_configure()
    elif args.cmd == "profile":
        _cmd_profile(args)
    elif args.cmd == "predict":
        _cmd_predict(args)
    elif args.cmd == "backtest":
        _cmd_backtest(args)
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
    if args.no_cache:
        pipeline._cache.disable()  # type: ignore
    result = pipeline.run(
        query=args.query,
        mode=mode,
        domain=domain,
        run_social=run_social,
        multi_sample=args.multi_sample,
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
    # Multi-sample uncertainty indicator
    multi_meta = result.metadata.get("multi_sample", {})
    if multi_meta.get("runs", 0) > 1:
        print(f"  Confidence Std:  {multi_meta.get('confidence_std', 0):.4f} (over {multi_meta['runs']} runs)")
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
        # Include baseline if present
        if result.metadata.get("baseline"):
            out["baseline"] = result.metadata["baseline"]
        # Include multi-sample if present
        if result.metadata.get("multi_sample"):
            out["multi_sample"] = result.metadata["multi_sample"]
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


def _cmd_profile(args):
    from smf_swarm.resource_profiler import run_profiler, get_current_profile, reset_profile
    from smf_swarm.resource_profiler.prompter import format_profile_table
    from smf_swarm.resource_profiler.detector import detect_hardware
    from smf_swarm.resource_profiler.registry import filter_available_profiles, recommend_profile

    if args.reset:
        reset_profile()
        print("✅ Profile lock cleared. Run 'smf-swarm profile' to re-detect.")
        return

    if args.show:
        current = get_current_profile()
        if current:
            print(f"\nCurrent profile: {current.get('name', 'not set')}")
            print(f"  Agents: {current.get('agent_count')}")
            print(f"  Steps:  {current.get('max_steps')}")
            print(f"  Model:  {current.get('llm_model')}")
            print(f"  Locked: {current.get('locked', False)}")
        else:
            print("\nNo profile configured yet. Run 'smf-swarm profile' to set one.")
        return

    # Run the profiler
    profile = run_profiler(auto=args.auto)
    print(f"\nProfile '{profile.display_name}' applied successfully.")


def _cmd_web(args):
    from smf_swarm.web.app import run_server
    rate_limit = tuple(args.rate_limit) if args.rate_limit else None
    run_server(host=args.host, port=args.port, auth_token=args.token, rate_limit=rate_limit)


def _cmd_backtest(args):
    from smf_swarm.backtest import BacktestStore
    import json
    bt = BacktestStore()
    # Handle ground-truth update
    if args.truth_id:
        if not args.outcome:
            print("❌ --set-truth requires --outcome true|false")
            sys.exit(1)
        ok = bt.update_ground_truth(args.truth_id, args.outcome == "true")
        if ok:
            print(f"✅ Ground truth updated for {args.truth_id}")
        else:
            print(f"❌ Prediction ID not found: {args.truth_id}")
        return
    # Show calibration report
    report = bt.calibration_report(domain=args.domain, mode=args.mode)
    print(json.dumps(report, indent=2))
    print(f"\n  Total tracked predictions: {report['total']}")
    print(f"  Resolved with ground truth: {report['resolved']}")
    if report['accuracy'] is not None:
        print(f"  Accuracy (resolved): {report['accuracy']:.2%}")
    if report['brier_score'] is not None:
        print(f"  Brier score (resolved): {report['brier_score']:.4f}")
