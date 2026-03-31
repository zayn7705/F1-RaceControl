#!/usr/bin/env python3
"""
Interactive CLI for deterministic race replay.

Usage:
    python scripts/replay_cli.py --events data/sample_events_hungary_2022.jsonl
"""

import argparse
import json
import sys
import threading
from pathlib import Path
from typing import Dict, List

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from replay.controller import ReplayController  # type: ignore  # noqa: E402
from replay.snapshot_io import save_snapshot  # type: ignore  # noqa: E402
from strategy.engine import StrategyEngine  # type: ignore  # noqa: E402
from strategy.logger import StrategyJsonlLogger  # type: ignore  # noqa: E402


def _derive_race_id(events_path: str) -> str:
    """Derive race_id from events filename stem."""
    stem = Path(events_path).stem
    for prefix in ("sample_events_", "events_", "sample_"):
        if stem.startswith(prefix):
            stem = stem[len(prefix) :]
            break
    stem = stem.replace(" ", "_").lower()
    return stem if stem else "unknown_race"


def load_events_from_jsonl(path: str) -> List[Dict]:
    """Load canonical events from a JSONL file."""
    events: List[Dict] = []
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Events file not found: {path}")

    with p.open("r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))

    # Basic invariant: seq should be monotonic if present
    seq_values = [e.get("seq") for e in events if "seq" in e]
    if seq_values and seq_values != sorted(seq_values):
        print("WARNING: seq values are not monotonic; engine will still use list order.", file=sys.stderr)

    return events


def print_help() -> None:
    print(
        """
Available commands:
  help                     Show this help message
  play                     Start/resume playback
  pause                    Pause playback
  step [n]                 Apply 1 (or n) events and print status
  rewind <seconds>         Rewind by given race time in seconds
  ff <seconds>             Fast-forward by given race time in seconds
  jump_time <seconds>      Jump to an absolute race time (seconds)
  speed <multiplier>       Set playback speed (e.g., 2.0 for 2x)
  snapshot [seconds]       Capture state and save to snapshots/{race_id}/
  status                   Print current race state summary
  quit                     Exit the program
"""
    )


def repl(controller: ReplayController, race_id: str, snapshots_dir: Path) -> None:
    """Simple command-line REPL for controlling replay."""
    print_help()
    controller.print_status()

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            continue

        parts = line.split()
        cmd = parts[0].lower()
        args = parts[1:]

        try:
            if cmd in ("quit", "exit", "q"):
                controller.stop()
                break
            # Pause simulation for any command other than 'play'
            if cmd != "play":
                controller.pause()

            if cmd == "help":
                print_help()
            elif cmd == "play":
                controller.play()
            elif cmd == "pause":
                controller.pause()
            elif cmd == "step":
                n = int(args[0]) if args else 1
                controller.step(n)
            elif cmd == "rewind":
                if not args:
                    print("Usage: rewind <seconds>")
                    continue
                seconds = float(args[0])
                controller.rewind(seconds)
            elif cmd in ("ff", "fast_forward"):
                if not args:
                    print("Usage: ff <seconds>")
                    continue
                seconds = float(args[0])
                controller.fast_forward(seconds)
            elif cmd in ("jump_time", "jt"):
                if not args:
                    print("Usage: jump_time <seconds>")
                    continue
                t = float(args[0])
                controller.jump_time(t)
            elif cmd == "speed":
                if not args:
                    print("Usage: speed <multiplier>")
                    continue
                speed = float(args[0])
                controller.set_speed(speed)
                print(f"Playback speed set to {speed}x")
            elif cmd == "status":
                controller.print_status()
            elif cmd == "snapshot":
                if args:
                    t = float(args[0])
                    controller.jump_time(t)
                state = controller.engine.get_state()
                path = save_snapshot(state, race_id, snapshots_dir)
                print(f"Snapshot saved to {path}")
            else:
                print(f"Unknown command: {cmd}. Type 'help' for a list of commands.")
        except ValueError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic F1 race replay CLI")
    parser.add_argument("--events", type=str, required=True, help="Path to JSONL events file")
    parser.add_argument(
        "--race-id",
        type=str,
        default=None,
        help="Race identifier for snapshot subfolder (default: derived from events filename)",
    )
    parser.add_argument(
        "--snapshot-interval",
        type=int,
        default=50,
        help="Number of events between snapshots (default: 50)",
    )
    parser.add_argument(
        "--initial-speed",
        type=float,
        default=1.0,
        help="Initial playback speed multiplier (default: 1.0)",
    )

    args = parser.parse_args()

    events = load_events_from_jsonl(args.events)
    if not events:
        print("No events loaded; exiting.")
        sys.exit(1)

    race_id = args.race_id if args.race_id else _derive_race_id(args.events)
    snapshots_dir = Path(__file__).parent.parent / "snapshots"
    data_dir = Path(__file__).parent.parent / "data"

    strategy_engine = StrategyEngine(emit_every_laps=5)
    strategy_logger = StrategyJsonlLogger(base_dir=data_dir)

    def on_state_update(state):
        recs = strategy_engine.observe(state, race_id=race_id)
        if recs:
            strategy_logger.append(race_id=race_id, recs=recs)

    controller = ReplayController(
        events,
        snapshot_interval_events=args.snapshot_interval,
        initial_speed=args.initial_speed,
        on_state_update=on_state_update,
    )

    try:
        repl(controller, race_id, snapshots_dir)
    finally:
        controller.stop()


if __name__ == "__main__":
    main()

