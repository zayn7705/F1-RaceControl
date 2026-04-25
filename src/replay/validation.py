from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from .state import RaceState


def validate_event_stream(events: list) -> list[str]:
    """Validate event stream (monotonic time, seq). Returns list of issue messages."""
    issues: list[str] = []
    prev_time = -1.0
    prev_seq = -1
    for i, ev in enumerate(events):
        t = ev.get("event_time")
        if t is not None:
            t = float(t)
            if t < prev_time:
                issues.append(f"event index {i}: event_time {t} < previous {prev_time} (out of order)")
            prev_time = t
        seq = ev.get("seq")
        if seq is not None and seq != i:
            issues.append(f"event index {i}: seq={seq} expected {i}")
        prev_seq = seq if seq is not None else prev_seq
        if "event_type" not in ev:
            issues.append(f"event index {i}: missing event_type")
    return issues


def check_state(state: RaceState, event_index: int) -> list[str]:
    """Run consistency checks on state at a given event index. Returns list of issue messages."""
    issues: list[str] = []
    drivers = list(state.drivers.values())

    # Per lap: at most one driver should have position==1 (impossible in real F1)
    by_lap = defaultdict(list)
    for d in drivers:
        if d.lap > 0:
            by_lap[d.lap].append(d)
    for lap, group in by_lap.items():
        pos_one = [d.driver_code for d in group if d.position == 1]
        if len(pos_one) > 1:
            issues.append(f"event {event_index} lap {lap}: multiple P1: {pos_one}")

    return issues

