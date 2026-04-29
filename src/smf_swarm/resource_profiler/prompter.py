"""Terminal prompter for user profile selection.

Handles interactive and auto modes. Purely I/O — no business logic.
"""

from __future__ import annotations

import sys
from typing import Callable

from .detector import HardwareProfile
from .registry import SwarmProfile, estimate_duration


def prompt_profile(
    hw: HardwareProfile,
    available: list[SwarmProfile],
    recommended: SwarmProfile,
    input_func: Callable[[str], str] | None = None,
    output_func: Callable[[str], None] | None = None,
) -> SwarmProfile:
    """Display hardware, available profiles, and prompt for choice.

    Returns the chosen SwarmProfile.
    """
    _in = input_func or input
    _out = output_func or (lambda s: print(s, file=sys.stdout))

    _out("")
    _print_header(_out)
    _print_hardware(hw, _out)
    _out("")

    _print_profiles(available, recommended, hw, _out)
    _out("")

    choice = _ask_choice(available, recommended, _in, _out)
    selected = _resolve_choice(choice, available, recommended)

    _out(f"\n✅ Swarm profile set to: {selected.display_name}")
    _out(f"   {selected.agent_count} agents × {selected.max_steps} steps")
    _out(f"   Model: {selected.llm_model} | Est. time: {estimate_duration(selected)}")

    return selected


# ── Output Formatting ────────────────────────────


def _print_header(out: Callable[[str], None]) -> None:
    out("══════════════════════════════════════════════════════════════")
    out("      SMF Swarm — Hardware & Swarm Profile Setup")
    out("══════════════════════════════════════════════════════════════")


def _print_hardware(hw: HardwareProfile, out: Callable[[str], None]) -> None:
    out("\n  Detected hardware:")
    out(
        f"    • RAM: {hw.total_ram_gb:.1f} GB total ({hw.available_ram_gb:.1f} GB available)"
    )
    out(f"    • CPU: {hw.cpu_cores} cores ({hw.cpu_threads} threads)")
    if hw.has_gpu:
        out(f"    • GPU: {hw.gpu_name} ({hw.vram_gb:.1f} GB VRAM)")
    else:
        out("    • GPU: Not detected (CPU inference)")
    out(f"    • OS:  {hw.os_name} {hw.os_version}")


def _print_profiles(
    available: list[SwarmProfile],
    recommended: SwarmProfile,
    hw: HardwareProfile,
    out: Callable[[str], None],
) -> None:
    out(f"\n  Recommended profile: [{recommended.priority}] {recommended.display_name}")
    out("\n  Choose your swarm profile:\n")

    from .registry import ALL_PROFILES

    for idx, p in enumerate(ALL_PROFILES, start=1):
        marker = ""
        lock = ""
        can_run = p in available
        is_rec = p.name == recommended.name

        if is_rec:
            marker = "  ←  RECOMMENDED"
        if not can_run:
            lock = "  [UNAVAILABLE — requires more RAM]"

        status_icon = "✓" if can_run else "✗"
        avail_note = (
            f"available ({p.ram_target_gb:.0f} GB target)"
            if can_run
            else f"needs {p.ram_min_gb:.0f}+ GB RAM"
        )

        out(
            f"    [{idx}] {p.display_name:<18}  {status_icon} {avail_note}{marker}{lock}"
        )
        out(f"        {p.agent_count} agents, {p.max_steps} steps, {p.llm_model}")
        out(f"        {p.description} — est. {estimate_duration(p)}")
        out("")

    custom_idx = len(ALL_PROFILES) + 1
    out(f"    [{custom_idx}] Custom — Define agent count, steps, and model manually")
    out(f"\n    Press Enter to accept the recommended profile [{recommended.priority}]")


def _ask_choice(
    available: list[SwarmProfile],
    recommended: SwarmProfile,
    _in: Callable[[str], str],
    out: Callable[[str], None],
) -> str:
    from .registry import ALL_PROFILES

    max_idx = len(ALL_PROFILES) + 1
    rec_idx = recommended.priority

    while True:
        raw = _in(f"\n  Your choice [1-{max_idx}, Enter={rec_idx}]: ").strip()
        if not raw:
            return str(rec_idx)
        if raw.isdigit():
            val = int(raw)
            if 1 <= val <= max_idx:
                if val <= len(ALL_PROFILES):
                    chosen = ALL_PROFILES[val - 1]
                    if chosen in available:
                        return str(val)
                    else:
                        out(
                            f"    ⚠ {chosen.display_name} requires {chosen.ram_min_gb:.0f}+ GB RAM."
                        )
                        confirm = _in("    Use anyway? [y/N]: ").strip().lower()
                        if confirm == "y":
                            return str(val)
                        continue
                else:
                    return str(val)  # Custom
        out(
            f"    ⚠ Invalid choice. Enter a number 1-{max_idx}, or press Enter for default."
        )


def _resolve_choice(
    choice_str: str,
    available: list[SwarmProfile],
    recommended: SwarmProfile,
) -> SwarmProfile:
    from .registry import ALL_PROFILES

    idx = int(choice_str)
    if idx <= len(ALL_PROFILES):
        return ALL_PROFILES[idx - 1]
    # Custom: delegate back
    return _prompt_custom_profile()


def _prompt_custom_profile() -> SwarmProfile:
    """Interactive custom profile builder."""
    print("\n  ── Custom Profile Builder ──")
    agents = int(input("  Agent count (e.g., 5-20): ").strip())
    steps = int(input("  Max steps per agent (e.g., 50-400): ").strip())
    model = input("  Model name (e.g., qwen2.5:7b): ").strip()
    model = model or "qwen2.5:7b"

    ctx = input("  Context length [8192]: ").strip()
    ctx_len = int(ctx) if ctx else 8192

    return SwarmProfile(
        name="custom",
        display_name="Custom",
        ram_target_gb=0,  # Unknown
        ram_min_gb=0,
        agent_count=agents,
        max_steps=steps,
        llm_model=model,
        llm_context_length=ctx_len,
        description="User-defined custom profile",
        use_case="Custom configuration",
        priority=0,
    )


def format_profile_table(
    hw: HardwareProfile,
    available: list[SwarmProfile],
    recommended: SwarmProfile,
) -> str:
    """Return a plain-text table for display in non-interactive contexts."""
    lines = [
        "SMF Swarm Profile Summary",
        "─" * 50,
        f"Hardware: {hw.total_ram_gb:.1f} GB RAM, {hw.cpu_cores} cores",
        f"GPU: {hw.gpu_name or 'None'} ({hw.vram_gb or 0:.1f} GB VRAM)",
        "",
        "Available Profiles:",
    ]
    for p in available:
        rec_mark = " ★" if p.name == recommended.name else ""
        lines.append(
            f"  {p.display_name:<20} {p.agent_count} agents × {p.max_steps} steps{rec_mark}"
        )
    return "\n".join(lines)
