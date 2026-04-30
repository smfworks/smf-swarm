#!/usr/bin/env python3
"""SMF Swarm — DeepSeek V4 Pro Ollama wrapper.

Usage:
    python smf_deepseek_wrapper.py "your coding prompt here"
    MODEL_NAME=deepseek-v4-pro:cloud python smf_deepseek_wrapper.py "..."

Why this wrapper exists:
    DeepSeek V4 Pro via Ollama defaults to num_predict=2048, which truncates
    code output mid-function. This script enforces num_predict=4096 and
    temperature=0.6 (empirically validated). It also retries on empty
    responses — a known failure mode in cloud-tunnelled Ollama manifests.
"""

from __future__ import annotations

import os
import sys
import subprocess
import time
import textwrap
from pathlib import Path

DEFAULT_MODEL = "deepseek-v4-pro:cloud"
NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "4096"))
TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.6"))
MAX_RETRIES = int(os.getenv("OLLAMA_MAX_RETRIES", "3"))
TIMEOUT_S = int(os.getenv("OLLAMA_TIMEOUT", "180"))


def _build_modelfile(model: str) -> str:
    """Return a Modelfile string tuned for DeepSeek coding."""
    return textwrap.dedent(
        f"""\
        FROM {model}
        PARAMETER num_predict {NUM_PREDICT}
        PARAMETER temperature {TEMPERATURE}
        PARAMETER top_p 0.9
        SYSTEM You are a senior software engineer. Write clean, idiomatic, production-ready code with comprehensive error handling, type hints, and docstrings. Prefer explicit over implicit. Validate all assumptions.
        """
    )


def _ensure_custom_model(model: str = DEFAULT_MODEL) -> str:
    """Create a tuned Ollama model if it doesn't exist."""
    custom_name = f"smf-deepseek-{NUM_PREDICT}"
    result = subprocess.run(
        ["ollama", "list"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ollama list failed: {result.stderr}")

    if custom_name in result.stdout:
        return custom_name

    # Build and register
    modelfile = _build_modelfile(model)
    mf_path = Path(f"/tmp/{custom_name}.modelfile")
    mf_path.write_text(modelfile)

    create = subprocess.run(
        ["ollama", "create", custom_name, "-f", str(mf_path)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if create.returncode != 0:
        raise RuntimeError(f"ollama create failed: {create.stderr}")

    print(f"✅ Created tuned Ollama model: {custom_name} (num_predict={NUM_PREDICT}, temp={TEMPERATURE})")
    return custom_name


def query(prompt: str, model: str | None = None) -> str:
    """Query DeepSeek via Ollama with retry logic for empty responses."""
    if model is None:
        model = os.getenv("MODEL_NAME", DEFAULT_MODEL)

    # Use custom tuned model if running the default
    if model == DEFAULT_MODEL:
        model = _ensure_custom_model(DEFAULT_MODEL)

    for attempt in range(1, MAX_RETRIES + 1):
        start = time.monotonic()
        try:
            proc = subprocess.run(
                ["ollama", "run", model, "--nowordwrap"],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_S,
            )
        except subprocess.TimeoutExpired:
            print(f"⏱ Attempt {attempt}/{MAX_RETRIES}: timed out after {TIMEOUT_S}s", file=sys.stderr)
            if attempt == MAX_RETRIES:
                raise
            time.sleep(2 ** attempt)  # exponential backoff
            continue

        elapsed = time.monotonic() - start
        output = proc.stdout.strip()

        if proc.returncode != 0:
            err = proc.stderr.strip()
            print(f"❌ Attempt {attempt}/{MAX_RETRIES}: ollama error ({proc.returncode}): {err}", file=sys.stderr)
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"ollama run failed after {MAX_RETRIES} attempts: {err}")
            time.sleep(2 ** attempt)
            continue

        if not output:
            print(f"⚠ Attempt {attempt}/{MAX_RETRIES}: empty response ({elapsed:.1f}s)", file=sys.stderr)
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"Empty response after {MAX_RETRIES} attempts")
            time.sleep(2 ** attempt)
            continue

        # Success
        print(f"✅ Response received in {elapsed:.1f}s ({len(output)} chars)")
        return output

    # Unreachable, but keeps type checker happy
    raise RuntimeError("Unexpected end of retry loop")


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if len(argv) < 1:
        print(f"Usage: {sys.argv[0]} 'Your coding prompt here'")
        print(f"Environment: MODEL_NAME, OLLAMA_NUM_PREDICT (default {NUM_PREDICT}), OLLAMA_TEMPERATURE (default {TEMPERATURE})")
        return 1

    prompt = " ".join(argv)
    try:
        result = query(prompt)
        print("\n" + "=" * 60)
        print(result)
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\nFatal: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
