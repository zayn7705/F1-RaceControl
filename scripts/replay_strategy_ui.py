#!/usr/bin/env python3
"""
Single-screen dashboard: race state + strategy + optional live metrics (dark theme).

Requires: pip install rich

Usage:
    python scripts/replay_strategy_ui.py --events data/sample_events_hungary_2022.jsonl
    python scripts/replay_strategy_ui.py --events data/sample_events_hungary_2022.jsonl \\
        --metrics-json telemetry_report.json
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from replay.controller import ReplayController  # noqa: E402
from replay.formatting import format_header, running_order  # noqa: E402
from replay.run_telemetry import RunTelemetry  # noqa: E402
from replay.state import RaceState  # noqa: E402
from replay.validation import check_state, validate_event_stream  # noqa: E402
from strategy.engine import StrategyEngine  # noqa: E402
from strategy.logger import StrategyJsonlLogger  # noqa: E402


def _derive_race_id(events_path: str) -> str:
    stem = Path(events_path).stem
    for prefix in ("sample_events_", "events_", "sample_"):
        if stem.startswith(prefix):
            stem = stem[len(prefix) :]
            break
    stem = stem.replace(" ", "_").lower()
    return stem if stem else "unknown_race"


def load_events_from_jsonl(path: str) -> List[Dict]:
    events: List[Dict] = []
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Events file not found: {path}")
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def _try_import_rich():
    try:
        from rich import box as rich_box
        from rich.columns import Columns
        from rich.console import Console, Group
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text
        return rich_box, Columns, Console, Group, Panel, Table, Text
    except ImportError as e:
        raise SystemExit(
            "The strategy UI requires the 'rich' package.\n"
            "  pip install rich\n"
            f"Original error: {e}"
        ) from e


def _fmt_ms(s: Optional[float]) -> str:
    if s is None:
        return "—"
    return f"{s * 1000:.3f}ms"


def _dashboard_theme() -> Any:
    from rich.theme import Theme

    return Theme(
        {
            "dash.title": "bold #7aa2f7",
            "dash.label": "#565f89",
            "dash.value": "#c0caf5",
            "dash.strong": "bold #c0caf5",
            "dash.muted": "dim #565f89",
            "dash.accent": "#bb9af7",
            "dash.ok": "#9ece6a",
            "dash.warn": "#e0af68",
            "dash.bad": "#f7768e",
            "dash.play": "bold #7dcfff",
            "dash.pause": "dim #c0caf5",
            "dash.header": "bold #7aa2f7",
            "dash.border": "#3b4261",
        }
    )


def _driver_table(
    state: RaceState,
    box: Any,
    Table: Any,
    *,
    limit: int | None,
    dark: bool,
) -> Any:
    header_style = "dash.header" if dark else "bold cyan"
    border = "dash.border" if dark else "dim"

    t = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style=header_style,
        border_style=border,
        expand=True,
        pad_edge=False,
    )
    t.add_column("Pos", justify="right", style="dash.strong" if dark else "bold", width=3)
    t.add_column("Drv", style="dash.value" if dark else "white", width=4)
    t.add_column("Lap", justify="right", width=3)
    t.add_column("Gap", width=7)
    t.add_column("Tire", width=6)
    t.add_column("St", width=3)
    t.add_column("Ag", width=3)
    t.add_column("Last", width=8)

    drivers = running_order(state.drivers.values())
    if limit:
        drivers = drivers[:limit]

    for i, d in enumerate(drivers, start=1):
        gap = f"{d.gap_to_leader_s:5.2f}" if d.gap_to_leader_s is not None else "  —"
        tire = (d.compound or "—")[:6]
        stint = str(d.stint) if d.stint is not None else "—"
        age = str(d.tire_age_laps) if d.tire_age_laps is not None else "—"
        last_lap = f"{d.last_lap_time_s:6.3f}" if d.last_lap_time_s is not None else "   —"
        t.add_row(str(i), d.driver_code, str(d.lap or 0), gap, tire, stint, age, last_lap)
    return t


def _strategy_table(rows: List[Dict[str, Any]], box: Any, Text: Any, *, dark: bool) -> Any:
    from rich.table import Table

    t = Table(
        box=box.SIMPLE,
        show_header=True,
        header_style="dash.accent" if dark else "bold magenta",
        border_style="dash.border" if dark else "dim",
        expand=True,
        padding=(0, 1),
    )
    t.add_column("Lp", style="dash.muted" if dark else "dim", width=3)
    t.add_column("Drv", width=4)
    t.add_column("Call", width=9)
    t.add_column("Pit", width=9)
    t.add_column("SC", width=10)
    t.add_column("Tire", width=6)

    for row in rows:
        feat = row.get("features") or {}
        rec = row.get("recommendation", "—")
        style = "dash.muted" if dark else "dim"
        if rec == "undercut":
            style = "dash.ok" if dark else "bold green"
        elif rec == "overcut":
            style = "dash.warn" if dark else "bold yellow"
        t.add_row(
            str(row.get("lap", "—")),
            str(row.get("driver", "—")),
            Text(str(rec), style=style),
            str(feat.get("pit_window", "—"))[:9],
            str(feat.get("safety_car_trigger", "—"))[:10],
            str(feat.get("compound") or "—")[:6],
        )
    return t


def _metrics_strip(
    telemetry: RunTelemetry,
    metrics_json: Optional[str],
    Text: Any,
    Group: Any,
    *,
    dark: bool,
) -> Any:
    lat = telemetry.apply_latency_live()
    wall = telemetry.elapsed_wall_s()
    eps = (telemetry.events_applied / wall) if wall > 0 else None
    eps_s = f"{eps:.0f}" if eps is not None else "—"

    line1 = Text.assemble(
        ("evt ", "dash.label" if dark else "dim"),
        (f"{telemetry.events_applied}/{telemetry.total_events}  ", "dash.value" if dark else ""),
        (f"{eps_s} ev/s  ", "dash.value" if dark else ""),
        ("p50 ", "dash.label" if dark else "dim"),
        (_fmt_ms(lat.p50_s), "dash.play" if dark else "cyan"),
        ("  p95 ", "dash.label" if dark else "dim"),
        (_fmt_ms(lat.p95_s), "dash.play" if dark else "cyan"),
        ("  p99 ", "dash.label" if dark else "dim"),
        (_fmt_ms(lat.p99_s), "dash.muted" if dark else "dim"),
    )
    issues = (
        f"stream_issues={telemetry.stream_issue_count} "
        f"state_issues={telemetry.state_issue_count} "
        f"exceptions={telemetry.exception_count}"
    )
    line2 = Text(
        issues + (f"  → JSON: {metrics_json}" if metrics_json else ""),
        style="dash.muted" if dark else "dim",
    )
    return Group(line1, line2)


def _build_dashboard(
    state: Optional[RaceState],
    strategy_rows: List[Dict[str, Any]],
    race_complete: bool,
    race_id: str,
    events_path: str,
    playing: bool,
    speed: float,
    telemetry: Optional[RunTelemetry],
    metrics_json: Optional[str],
    box: Any,
    Columns: Any,
    Group: Any,
    Panel: Any,
    Table: Any,
    Text: Any,
    *,
    dark: bool,
    max_drivers: int,
    max_strat_rows: int,
) -> Any:
    if state is None or not state.drivers:
        race_panel_inner: Any = Text(
            "No drivers yet — step or play.",
            style="dash.muted" if dark else "italic dim",
        )
    else:
        tbl = _driver_table(state, box, Table, limit=max_drivers, dark=dark)
        hdr = Text(format_header(state), style="dash.value" if dark else "bold white")
        race_panel_inner = Group(hdr, Text(""), tbl)

    strat_slice = strategy_rows[-max_strat_rows:] if strategy_rows else []
    if strat_slice:
        st = _strategy_table(strat_slice, box, Text, dark=dark)
        strat_inner = Group(
            Text("Strategy (latest)", style="dash.accent" if dark else "bold magenta"),
            Text(""),
            st,
        )
    else:
        strat_inner = Text(
            "No strategy rows yet (every 5 laps + SC/VSC transitions).",
            style="dash.muted" if dark else "italic dim",
        )

    mode_s = "PLAY" if playing else "PAUSE"
    mode_style = "dash.play" if (playing and dark) else ("dash.pause" if dark else ("bold cyan" if playing else "dim"))
    status_bits: List[Any] = [
        ("Race ", "dash.label" if dark else "dim"),
        (race_id, "dash.title" if dark else "bold cyan"),
        ("  ", ""),
        (mode_s, mode_style),
        (f"  speed×{speed:g}  ", "dash.value" if dark else ""),
        (Path(events_path).name, "dash.muted" if dark else "dim"),
    ]
    if race_complete:
        status_bits.append(("  FINISHED", "dash.ok" if dark else "bold green"))
    status_line = Text.assemble(*status_bits)

    metrics_block: Any
    if telemetry is not None:
        metrics_block = Panel(
            _metrics_strip(telemetry, metrics_json, Text, Group, dark=dark),
            title=Text("Performance", style="dash.header" if dark else "bold"),
            border_style="dash.border" if dark else "dim",
            padding=(0, 1),
        )
    else:
        metrics_block = Text(
            "Tip: add --metrics-json report.json for live latency (p50/p95) and throughput.",
            style="dash.muted" if dark else "dim",
        )

    twin = Columns(
        [
            Panel(
                race_panel_inner,
                title=Text("Race state", style="dash.header" if dark else "bold cyan"),
                border_style="dash.border" if dark else "cyan",
                padding=(0, 1),
            ),
            Panel(
                strat_inner,
                title=Text("Strategy engine", style="dash.accent" if dark else "bold magenta"),
                border_style="dash.border" if dark else "magenta",
                padding=(0, 1),
            ),
        ],
        expand=True,
        equal=False,
    )

    log_hint = Text(
        f"Logged to data/strategy_recs_{race_id}.jsonl",
        style="dash.muted" if dark else "dim",
    )
    footer = Text(
        "step [n] | play | pause | speed <x> | quit | help — empty line = refresh",
        style="dash.muted" if dark else "dim",
    )
    if race_complete:
        footer = Text("Race complete — type quit to exit.", style="dash.ok" if dark else "bold green")

    body = Group(
        status_line,
        Text(""),
        metrics_block,
        Text(""),
        twin,
        Text(""),
        log_hint,
        Text(""),
        footer,
    )

    title = "[dash.title]RaceControl[/] — [dash.value]one-screen dashboard[/]"
    if not dark:
        title = "[bold cyan]RaceControl[/] — [white]one-screen dashboard[/]"

    return Panel(
        body,
        title=title,
        border_style="dash.border" if dark else "cyan",
        style="on #16161e" if dark else "",
        padding=(1, 2),
    )


def main() -> None:
    box, Columns, Console, Group, Panel, Table, Text = _try_import_rich()

    parser = argparse.ArgumentParser(description="Replay dashboard: state + strategy + metrics")
    parser.add_argument("--events", type=str, required=True, help="Path to JSONL events file")
    parser.add_argument("--race-id", type=str, default=None)
    parser.add_argument("--snapshot-interval", type=int, default=50)
    parser.add_argument("--initial-speed", type=float, default=20.0)
    parser.add_argument("--metrics-json", type=str, default=None, help="Write run metrics JSON; enables live stats strip")
    parser.add_argument(
        "--check-every",
        type=int,
        default=0,
        help="State consistency checks every N events (0 = only at end when metrics enabled)",
    )
    parser.add_argument(
        "--light",
        action="store_true",
        help="Light terminal theme instead of default dark dashboard",
    )
    parser.add_argument(
        "--max-drivers",
        type=int,
        default=18,
        help="Max rows in the running-order table (default fits one screen)",
    )
    parser.add_argument(
        "--max-strategy-rows",
        type=int,
        default=14,
        help="Max recent strategy emissions to show",
    )
    args = parser.parse_args()
    dark = not args.light

    events = load_events_from_jsonl(args.events)
    if not events:
        print("No events loaded.", file=sys.stderr)
        sys.exit(1)

    race_id = args.race_id or _derive_race_id(args.events)
    data_dir = Path(__file__).parent.parent / "data"

    strategy_engine = StrategyEngine(emit_every_laps=5)
    strategy_logger = StrategyJsonlLogger(base_dir=data_dir)
    strat_rows: Deque[Dict[str, Any]] = deque(maxlen=80)
    ui_lock = threading.Lock()
    shared: Dict[str, Any] = {
        "state": None,
        "race_complete": False,
    }

    telemetry = RunTelemetry(race_id=race_id) if args.metrics_json else None
    if telemetry is not None:
        telemetry.record_stream_issues(validate_event_stream(events))

    def on_state_update(state: RaceState) -> None:
        recs = strategy_engine.observe(state, race_id=race_id)
        if recs:
            strategy_logger.append(race_id=race_id, recs=recs)
            for r in recs:
                with ui_lock:
                    strat_rows.append(StrategyEngine.to_json_dict(r))
        if telemetry is not None and args.check_every and state.current_event_index % args.check_every == 0:
            telemetry.record_state_issues(check_state(state, state.current_event_index))
        with ui_lock:
            shared["state"] = state
            if len(events) > 0 and state.current_event_index >= len(events) - 1:
                shared["race_complete"] = True

    controller = ReplayController(
        events,
        snapshot_interval_events=args.snapshot_interval,
        initial_speed=args.initial_speed,
        status_printer=lambda *_: None,
        on_state_update=on_state_update,
        exit_process_on_complete=False,
        telemetry=telemetry,
    )

    with ui_lock:
        shared["state"] = controller.engine.get_state()

    console = Console(theme=_dashboard_theme() if dark else Theme({}), highlight=False)

    def render() -> Any:
        with ui_lock:
            st = shared.get("state")
            rc = shared.get("race_complete", False)
            rows_copy = list(strat_rows)
        playing = controller.is_playing()
        spd = controller.playback_speed
        return _build_dashboard(
            st,
            rows_copy,
            rc,
            race_id,
            args.events,
            playing,
            spd,
            telemetry,
            args.metrics_json,
            box,
            Columns,
            Group,
            Panel,
            Table,
            Text,
            dark=dark,
            max_drivers=args.max_drivers,
            max_strat_rows=args.max_strategy_rows,
        )

    intro = (
        "[dash.muted]Main-thread input: type at[/] [dash.title]>[/] [dash.muted]after each draw. "
        "During play, press Enter to refresh; pause stops the background loop.[/]\n"
    )
    if not dark:
        intro = (
            "[dim]Main-thread input: type at[/] [bold]>[/] [dim]after each draw. "
            "During play, press Enter to refresh; pause stops the background loop.[/]\n"
        )
    console.print(intro)

    try:
        while True:
            with ui_lock:
                shared["state"] = controller.engine.get_state()
            console.clear()
            console.print(render())
            try:
                line = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not line:
                continue
            parts = line.split()
            cmd = parts[0].lower()
            rest = parts[1:]
            if cmd in ("q", "quit", "exit"):
                break
            if cmd == "help":
                continue
            if cmd == "play":
                controller.play()
            elif cmd == "pause":
                controller.pause()
            elif cmd == "speed":
                if rest:
                    controller.set_speed(float(rest[0]))
            elif cmd == "step":
                n = int(rest[0]) if rest else 1
                controller.pause()
                controller.step(n)
    finally:
        controller.stop()
        if telemetry is not None:
            if not args.check_every:
                st = controller.engine.get_state()
                telemetry.record_state_issues(check_state(st, st.current_event_index))
            report = telemetry.report()
            hdr = "Run metrics" if not dark else "[dash.title]Run metrics[/]"
            console.print(f"\n{hdr}")
            console.print(
                f"Completed: {report.completed} | Events: {report.events_applied}/{report.total_events} | "
                f"Wall: {report.wall_time_s:.3f}s | Throughput: {(report.events_per_s or 0.0):.1f} ev/s"
            )
            console.print(
                "apply_next_event latency (s): "
                f"p50={report.apply_next_event_latency.p50_s} "
                f"p90={report.apply_next_event_latency.p90_s} "
                f"p95={report.apply_next_event_latency.p95_s} "
                f"p99={report.apply_next_event_latency.p99_s}"
            )
            with open(args.metrics_json, "w", encoding="utf-8") as f:
                f.write(report.to_json(indent=2))
            console.print(f"Metrics JSON written to {args.metrics_json}")


if __name__ == "__main__":
    main()
