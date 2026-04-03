#!/usr/bin/env python3
"""
Interactive counterfactual strategy MVP — 2022 Hungary race (dry compounds).

Uses a simple deterministic model; results are simulated, not real-world counterfactuals.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from strategy_mvp.advisor import lap_advice  # noqa: E402
from strategy_mvp.benchmark import compute_benchmark  # noqa: E402
from strategy_mvp.constants import DEFAULT_HUNGARY_2022_JSONL  # noqa: E402
from strategy_mvp.index_events import build_race_index, load_events_jsonl  # noqa: E402
from strategy_mvp.physics_simple import normalize_compound  # noqa: E402
from strategy_mvp.player_state import PlayerState  # noqa: E402
from strategy_mvp.simulator import apply_player_step, simulated_position  # noqa: E402


DISCLAIMER = """
Note: All times and positions are produced by RaceControl’s simplified model.
Benchmark strategy = fastest among a finite set of candidate plans under that model,
not the real-world optimum. Rivals do not react to your stops.
"""


def _pick_driver(drivers: list[str], raw: str) -> Optional[str]:
    raw = raw.strip().upper()
    if raw in drivers:
        return raw
    if raw.isdigit():
        i = int(raw)
        if 1 <= i <= len(drivers):
            return drivers[i - 1]
    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hungary 2022 interactive strategy MVP (simulated counterfactual)"
    )
    parser.add_argument(
        "--events",
        type=str,
        default=str(DEFAULT_HUNGARY_2022_JSONL),
        help=f"Path to full-race JSONL (default: {DEFAULT_HUNGARY_2022_JSONL})",
    )
    args = parser.parse_args()

    path = Path(args.events)
    if not path.is_file():
        print(
            f"Events file not found: {path}\n"
            "Export full Hungary 2022 race data with:\n"
            "  python scripts/export_events.py --year 2022 --gp Hungary --session R "
            f"--out {DEFAULT_HUNGARY_2022_JSONL}",
            file=sys.stderr,
        )
        sys.exit(1)

    events = load_events_jsonl(path)
    index = build_race_index(events)
    if not index.drivers or index.max_lap < 2:
        print("Not enough lap data in events file.", file=sys.stderr)
        sys.exit(1)

    print(DISCLAIMER)
    print(f"Loaded {len(events)} events — {len(index.drivers)} drivers, {index.max_lap} laps.\n")

    print("Drivers:")
    for i, d in enumerate(index.drivers, start=1):
        print(f"  {i:2}  {d}")
    drv_in = input("Choose driver (number or code): ").strip()
    driver = _pick_driver(index.drivers, drv_in)
    if driver is None:
        print("Invalid driver.", file=sys.stderr)
        sys.exit(1)

    best_plan, best_time, ranked = compute_benchmark(index, driver)
    print("\n--- Pre-race candidate plans (model scores 0–100, not probabilities) ---")
    for i, (pl, tm, sc, rationale) in enumerate(ranked[:12], start=1):
        mark = "*" if pl.name == best_plan.name and abs(tm - best_time) < 1e-6 else " "
        print(f"{mark} {i:2}. score={sc:3d}  time={tm:10.2f}s  {pl.name}")
        print(f"      {rationale}")
    print(f"\nBenchmark (best among searched): {best_plan.name} — {best_time:.2f}s model time\n")

    start_c = input("Starting compound SOFT / MEDIUM / HARD [MEDIUM]: ").strip().upper() or "MEDIUM"
    start_c = normalize_compound(start_c) or "MEDIUM"
    intent = input("Optional: note an intended plan name from the list (or Enter to skip): ").strip()

    state = PlayerState(
        controlled_driver=driver,
        current_lap=1,
        compound=start_c,
        tire_age_laps=0,
        cumulative_time_s=0.0,
        pit_stops_used=0,
        pit_history=[],
        intended_plan_name=intent,
    )

    print("\nCommands: [Enter] / continue — next lap; pit SOFT|MEDIUM|HARD — pit before this lap; status; help; quit\n")

    aborted = False
    while state.current_lap <= index.max_lap:
        lap = state.current_lap
        st = index.status_for_driver_lap(driver, lap - 1) if lap > 1 else index.status_at_time(0.0)
        pos, n = simulated_position(index, driver, lap - 1, state.cumulative_time_s) if lap > 1 else (0, len(index.drivers))
        advice = lap_advice(index, state)

        pos_str = f"simulated P{pos}/{n} (end lap {lap - 1})" if lap > 1 else "—"
        print(f"--- Lap {lap}/{index.max_lap} — track ~{st} — cum {state.cumulative_time_s:.2f}s — {pos_str} ---")
        print(f"Advisor: {advice}")
        print(f"Tires: {state.compound} age {state.tire_age_laps}")

        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            aborted = True
            break

        if not line or line.lower() in ("c", "continue", "n", "next"):
            pit_arg = None
        elif line.lower() in ("q", "quit", "exit"):
            print("Stopped early — partial run.")
            _print_summary(index, state, best_plan, best_time, completed=False)
            return
        elif line.lower() == "status":
            print(f"  cumulative model time: {state.cumulative_time_s:.2f}s")
            print(f"  pits: {state.pit_stops_used}  history: {[p.before_lap for p in state.pit_history]}")
            continue
        elif line.lower() in ("h", "help"):
            print("  [Enter] advance one lap; pit SOFT|MEDIUM|HARD; status; quit")
            continue
        elif line.lower().startswith("pit "):
            rest = line[4:].strip()
            pit_arg = normalize_compound(rest)
            if pit_arg is None:
                print("  Unknown compound — use SOFT, MEDIUM, or HARD")
                continue
        else:
            print("  Unknown command (try help)")
            continue

        state = apply_player_step(index, state, pit_arg)

    race_completed = (not aborted) and (state.current_lap > index.max_lap)
    _print_summary(index, state, best_plan, best_time, completed=race_completed)


def _print_summary(index, state, best_plan, best_time: float, completed: bool) -> None:
    through = min(state.current_lap - 1, index.max_lap)
    pos, n = simulated_position(
        index, state.controlled_driver, through, state.cumulative_time_s
    )
    print("\n" + "=" * 60)
    print("END SUMMARY (simulated — see disclaimer)")
    print("=" * 60)
    if not completed:
        print(f"Stopped after lap {through} (not full distance).")
    print(f"Driver: {state.controlled_driver}")
    print(f"Your model race time: {state.cumulative_time_s:.2f}s")
    print(f"Benchmark model time (best searched): {best_time:.2f}s  ({best_plan.name})")
    delta = state.cumulative_time_s - best_time
    print(f"Delta vs benchmark: {delta:+.2f}s (positive = slower than benchmark)")
    print(f"Simulated finishing position (ordering only): P{pos} / {n}")
    print(f"Your pit stops: {state.pit_stops_used}  laps: {[p.before_lap for p in state.pit_history]}")
    print(f"Benchmark pits before laps: {best_plan.pit_before_laps}  compounds: {' -> '.join(best_plan.stint_compounds)}")
    if state.intended_plan_name:
        print(f"Your noted intent: {state.intended_plan_name}")
    print(DISCLAIMER)


if __name__ == "__main__":
    main()
