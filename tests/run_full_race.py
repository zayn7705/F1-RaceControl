#!/usr/bin/env python3
"""
Run a full race simulation from a JSONL events file and print final standings.
Also runs consistency checks over the simulation.

Usage:
    python scripts/run_full_race.py --events data/bahrain_2022_full.jsonl
"""

import argparse
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from replay.engine import RaceStateEngine
from replay.formatting import format_full_state, running_order
from replay.validation import check_state, validate_event_stream


def load_events(path: str) -> list:
    """Load canonical events from JSONL."""
    events = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full race simulation and print final standings")
    parser.add_argument("--events", type=str, required=True, help="Path to JSONL events file")
    parser.add_argument("--check-every", type=int, default=0, help="Run consistency checks every N events (0 = only at end)")
    args = parser.parse_args()

    events = load_events(args.events)
    if not events:
        print("No events loaded.", file=sys.stderr)
        sys.exit(1)

    stream_issues = validate_event_stream(events)
    if stream_issues:
        print("Event stream issues:", file=sys.stderr)
        for msg in stream_issues[:20]:
            print(f"  {msg}", file=sys.stderr)
        if len(stream_issues) > 20:
            print(f"  ... and {len(stream_issues) - 20} more", file=sys.stderr)

    print(f"Loaded {len(events)} events. Running simulation...")
    engine = RaceStateEngine(events, snapshot_interval_events=50)

    all_issues = []
    n = 0
    while True:
        state = engine.apply_next_event()
        if state is None:
            break
        n += 1
        if n % 400 == 0:
            print(f"  Applied {n} events...")
        if args.check_every and n % args.check_every == 0:
            all_issues.extend(check_state(engine.get_state(), engine.get_state().current_event_index))

    final = engine.get_state()
    all_issues.extend(check_state(final, final.current_event_index))

    print(f"\nApplied all {n} events. Final event index: {final.current_event_index}")
    print(f"Race time: {final.current_time_s:.1f} s ({final.current_time_s / 3600:.2f} h)")
    print(f"Track status: {final.track_status}")
    print(f"Drivers: {len(final.drivers)}")
    print("\n" + "=" * 60)
    print("FINAL STANDINGS (running order)")
    print("=" * 60)
    print(format_full_state(final, limit=None))

    if stream_issues or all_issues:
        print("\n" + "=" * 60)
        print("ISSUES FOUND")
        print("=" * 60)
        for msg in stream_issues[:30]:
            print(f"  [stream] {msg}")
        for msg in all_issues[:50]:
            print(f"  [state]  {msg}")
        if len(all_issues) > 50:
            print(f"  ... and {len(all_issues) - 50} more state issues")
        sys.exit(1)
    else:
        print("\nNo consistency issues reported.")
        sys.exit(0)


if __name__ == "__main__":
    main()
