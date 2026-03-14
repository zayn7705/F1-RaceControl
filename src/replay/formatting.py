from __future__ import annotations

from typing import Iterable, List

from .state import DriverState, RaceState


def format_header(state: RaceState) -> str:
    """Format a one-line header summarizing the current race state."""
    time_s = state.current_time_s
    idx = state.current_event_index
    total = state.total_events
    track_status = state.track_status or "UNKNOWN"
    return f"time={time_s:8.3f}s  event={idx + 1 if idx >= 0 else 0}/{total}  track_status={track_status}"


def running_order(drivers: Iterable[DriverState]) -> List[DriverState]:
    """
    Sort drivers in running order: most laps first, then by official position
    (when available), then by lap completion time (earlier = ahead), then driver code.
    Gives a unique race order (no duplicate positions); DNFs appear at end.
    """
    return sorted(
        drivers,
        key=lambda d: (
            -(d.lap or 0),  # more laps first
            d.position if d.position is not None else 999,  # use official position when available
            d.last_lap_complete_time_s if d.last_lap_complete_time_s is not None else float("inf"),
            d.driver_code,
        ),
    )


def _sorted_drivers(drivers: Iterable[DriverState]) -> List[DriverState]:
    """Alias for running_order for backward compatibility."""
    return running_order(drivers)


def format_driver_table(state: RaceState, limit: int | None = None) -> str:
    """Format a table of drivers in running order (unique POS 1, 2, 3, ...)."""
    drivers = running_order(state.drivers.values())
    if limit is not None and limit > 0:
        drivers = drivers[:limit]

    lines: List[str] = []
    header = "POS  DRV  LAP  GAP      TIRE      STINT  AGE  LAST_LAP"
    lines.append(header)
    lines.append("-" * len(header))

    for running_pos, d in enumerate(drivers, start=1):
        pos = running_pos  # unique running position (1, 2, 3, ...)
        gap = f"{d.gap_to_leader_s:6.3f}" if d.gap_to_leader_s is not None else "  --- "
        tire = d.compound or "-"
        stint = d.stint if d.stint is not None else "-"
        age = d.tire_age_laps if d.tire_age_laps is not None else "-"
        last_lap = f"{d.last_lap_time_s:7.3f}" if d.last_lap_time_s is not None else "   --- "

        lines.append(
            f"{pos:>3}  {d.driver_code:>3}  {d.lap:>3}  {gap}  {tire:<8}  {stint!s:>5}  {age!s:>3}  {last_lap}"
        )

    return "\n".join(lines)


def format_full_state(state: RaceState, limit: int | None = None) -> str:
    """Convenience wrapper to render header + table."""
    return f"{format_header(state)}\n{format_driver_table(state, limit=limit)}"

