#!/usr/bin/env python3
"""
Terminal UI: race state + strategy recommendations (original StrategyEngine).

Requires: pip install rich

Usage:
    python scripts/replay_strategy_ui.py --events data/sample_events_hungary_2022.jsonl
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
from replay.state import RaceState  # noqa: E402
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
        from rich.console import Console, Group
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        return rich_box, Console, Group, Panel, Text
    except ImportError as e:
        raise SystemExit(
            "The strategy UI requires the 'rich' package.\n"
            "  pip install rich\n"
            f"Original error: {e}"
        ) from e


def _driver_table(state: RaceState, box: Any, limit: int | None = 20) -> Any:
    from rich.table import Table

    t = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        expand=True,
    )
    t.add_column("Pos", justify="right", style="bold", width=4)
    t.add_column("Driver", style="white", width=5)
    t.add_column("Lap", justify="right", width=4)
    t.add_column("Gap", width=8)
    t.add_column("Tire", width=7)
    t.add_column("St", width=4)
    t.add_column("Age", width=4)
    t.add_column("Last lap", width=9)

    drivers = running_order(state.drivers.values())
    if limit:
        drivers = drivers[:limit]

    for i, d in enumerate(drivers, start=1):
        gap = f"{d.gap_to_leader_s:6.3f}" if d.gap_to_leader_s is not None else "  —"
        tire = d.compound or "—"
        stint = str(d.stint) if d.stint is not None else "—"
        age = str(d.tire_age_laps) if d.tire_age_laps is not None else "—"
        last_lap = f"{d.last_lap_time_s:7.3f}" if d.last_lap_time_s is not None else "   —"
        t.add_row(str(i), d.driver_code, str(d.lap), gap, tire, stint, age, last_lap)
    return t


def _strategy_table(rows: List[Dict[str, Any]], box: Any, Text: Any) -> Any:
    from rich.table import Table

    t = Table(
        box=box.SIMPLE,
        show_header=True,
        header_style="bold magenta",
        border_style="dim",
        expand=True,
        padding=(0, 1),
    )
    t.add_column("Lap", style="dim", width=4)
    t.add_column("Driver", width=5)
    t.add_column("Call", width=10)
    t.add_column("Pit window", width=11)
    t.add_column("SC", width=12)
    t.add_column("Tire", width=7)

    for row in rows:
        feat = row.get("features") or {}
        rec = row.get("recommendation", "—")
        style = "dim"
        if rec == "undercut":
            style = "bold green"
        elif rec == "overcut":
            style = "bold yellow"
        t.add_row(
            str(row.get("lap", "—")),
            str(row.get("driver", "—")),
            Text(str(rec), style=style),
            str(feat.get("pit_window", "—")),
            str(feat.get("safety_car_trigger", "—")),
            str(feat.get("compound") or "—"),
        )
    return t


def _build_layout(
    state: Optional[RaceState],
    strategy_rows: List[Dict[str, Any]],
    race_complete: bool,
    box: Any,
    Group: Any,
    Panel: Any,
    Text: Any,
) -> Any:
    if state is None or not state.drivers:
        race_block: Any = Text("No drivers yet — use step or play.", style="italic dim")
    else:
        race_block = Group(
            Text(format_header(state), style="bold white"),
            Text(""),
            _driver_table(state, box),
        )

    if strategy_rows:
        st = _strategy_table(strategy_rows[-18:], box, Text)
        strat_block = Group(
            Text("Latest strategy emissions", style="bold magenta"),
            st,
        )
    else:
        strat_block = Text(
            "No strategy rows yet (every 5 laps + SC/VSC transitions).",
            style="italic dim",
        )

    footer = Text(
        "Commands: step [n] | play | pause | speed <x> | quit | help — "
        "Empty line = refresh (e.g. during play).",
        style="dim",
    )
    if race_complete:
        footer = Text("Race complete. Type quit to exit.", style="bold green")

    body = Group(
        race_block,
        Text(""),
        strat_block,
        Text(""),
        footer,
    )

    return Panel(
        body,
        title="[bold cyan]RaceControl[/] — strategy + state",
        subtitle="[dim]Also logged to data/strategy_recs_<race_id>.jsonl[/]",
        border_style="cyan",
        padding=(1, 2),
    )


def main() -> None:
    box, Console, Group, Panel, Text = _try_import_rich()

    parser = argparse.ArgumentParser(description="Replay UI with strategy recommendations")
    parser.add_argument("--events", type=str, required=True, help="Path to JSONL events file")
    parser.add_argument("--race-id", type=str, default=None)
    parser.add_argument("--snapshot-interval", type=int, default=50)
    parser.add_argument("--initial-speed", type=float, default=20.0)
    args = parser.parse_args()

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

    def on_state_update(state: RaceState) -> None:
        recs = strategy_engine.observe(state, race_id=race_id)
        if recs:
            strategy_logger.append(race_id=race_id, recs=recs)
            for r in recs:
                with ui_lock:
                    strat_rows.append(StrategyEngine.to_json_dict(r))
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
    )

    with ui_lock:
        shared["state"] = controller.engine.get_state()

    console = Console()

    def render() -> Any:
        with ui_lock:
            st = shared.get("state")
            rc = shared.get("race_complete", False)
            rows_copy = list(strat_rows)
        return _build_layout(st, rows_copy, rc, box, Group, Panel, Text)

    console.print(
        "[dim]Main-thread input: type at [bold]>[/] after each screen update. "
        "Rich Live was removed so stdin works in VS Code / Cursor terminals. "
        "After [bold]play[/], press Enter to refresh, or [bold]pause[/] then Enter.[/]\n"
    )

    # One clear+draw per interaction: avoids stacked panels and broken background-thread stdin.
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


if __name__ == "__main__":
    main()
