"""SMF Swarm — CLI Rich rendering (optional [cli] extra).

Live dashboard with rich panels, progress, and tables.
Only activates if `rich` is installed.
"""

from __future__ import annotations

import time

from smf_swarm.pipeline import Pipeline, PipelineResult


def is_available() -> bool:
    try:
        import rich

        return True
    except ImportError:
        return False


def run_prediction_rich(
    query: str,
    mode: str,
    domain: str,
    multi_sample: int = 1,
    no_cache: bool = False,
) -> PipelineResult:
    """Run a prediction with rich live UI."""
    from rich.console import Console
    from rich.live import Live
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import (
        Progress,
        SpinnerColumn,
        TextColumn,
        BarColumn,
        TaskProgressColumn,
        TimeRemainingColumn,
    )
    from rich.layout import Layout
    from rich.text import Text
    from rich import box

    console = Console()
    pipeline = Pipeline()
    if no_cache:
        pipeline._cache.disable()

    # Layout
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=5),
        Layout(name="progress", size=6),
        Layout(name="body", ratio=1),
    )

    # Progress bar
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[yellow]{task.fields[node]}", justify="right"),
        BarColumn(bar_width=40),
        TaskProgressColumn(),
        TimeRemainingColumn(elapsed_when_finished=True),
        console=console,
        transient=True,
    )
    task = progress.add_task("[cyan]Pipeline", total=100, node="Idle")

    # Header
    header_text = Text()
    header_text.append("SMF Swarm", style="bold yellow")
    header_text.append("  |  ")
    header_text.append(
        f"Query: {query[:60]}{'...' if len(query) > 60 else ''}", style="white"
    )
    header_text.append("  |  ")
    header_text.append(f"Mode: {mode}", style="cyan")
    header_text.append("  |  ")
    header_text.append(f"Domain: {domain}", style="green")
    layout["header"].update(Panel(header_text, border_style="yellow", box=box.ROUNDED))
    layout["progress"].update(
        Panel(progress, border_style="cyan", box=box.ROUNDED, title="Progress")
    )

    # Body panel starts empty
    body_table = Table(box=box.ROUNDED, border_style="dim", pad_edge=False)
    body_table.add_column("Node", style="cyan", width=20)
    body_table.add_column("Status", style="white", width=12)
    body_table.add_column("Duration", style="yellow", width=10)
    body_table.add_column("Output", style="dim")
    layout["body"].update(
        Panel(body_table, border_style="blue", box=box.ROUNDED, title="Nodes")
    )

    results: list[dict] = []

    with Live(layout, console=console, refresh_per_second=4, screen=True):
        # Monkey-patch pipeline methods to capture progress
        original_run = pipeline._run_state_machine
        node_index = 0
        nodes = {
            "standard": [
                "data_gatherer",
                "feature_engineer",
                "reflection",
                "model_runner",
                "validator",
                "reporter",
            ],
            "debate": ["data_gatherer", "feature_engineer", "debate", "reporter"],
            "full": [
                "data_gatherer",
                "feature_engineer",
                "reflection",
                "model_runner",
                "validator",
                "debate",
                "merge",
                "social_simulation",
                "reporter",
            ],
        }.get(mode, [])
        total_nodes = len(nodes)

        def _patch_node(name: str, orig):
            def wrapped(state: dict):
                nonlocal node_index
                progress.update(task, node=name.replace("_", " ").title())
                body_table.add_row(
                    name.replace("_", " ").title(),
                    "[yellow]Running...",
                    "—",
                    "",
                )
                t0 = time.time()
                try:
                    result = orig(state)
                    duration = time.time() - t0
                    node_index += 1
                    pct = int((node_index / total_nodes) * 100) if total_nodes else 50
                    progress.update(
                        task, advance=100 / total_nodes if total_nodes else 10
                    )
                    body_table.rows[-1].columns[1]._text = [Text("Done", style="green")]
                    body_table.rows[-1].columns[2]._text = [
                        Text(f"{duration:.1f}s", style="yellow")
                    ]
                    return result
                except Exception as e:
                    body_table.rows[-1].columns[1]._text = [Text("Error", style="red")]
                    body_table.rows[-1].columns[3]._text = [
                        Text(str(e)[:60], style="red")
                    ]
                    raise

            return wrapped

        originals = {}
        for node_name in nodes:
            if hasattr(pipeline, f"_{node_name}"):
                originals[node_name] = getattr(pipeline, f"_{node_name}")
                setattr(
                    pipeline,
                    f"_{node_name}",
                    _patch_node(node_name, originals[node_name]),
                )

        try:
            result = pipeline.run(
                query=query, mode=mode, domain=domain, multi_sample=multi_sample
            )
        finally:
            for node_name, orig in originals.items():
                setattr(pipeline, f"_{node_name}", orig)

        # Final panel
        progress.update(task, completed=100, node="Done")
        final_table = Table(box=box.ROUNDED, border_style="green")
        final_table.add_column("Metric", style="cyan", width=18)
        final_table.add_column("Value", style="white")
        final_table.add_row("Confidence", f"[bold yellow]{result.confidence:.2f}")
        final_table.add_row("Data Quality", f"{result.data_quality:.2f}")
        final_table.add_row("Duration", f"{result.duration_s:.0f}s")
        final_table.add_row("Health", f"{result.health_score:.1f}")
        final_table.add_row(
            "Summary",
            result.summary[:200] + ("..." if len(result.summary) > 200 else ""),
        )
        layout["body"].update(
            Panel(final_table, border_style="green", box=box.ROUNDED, title="Result")
        )
        time.sleep(1.5)

    return result
