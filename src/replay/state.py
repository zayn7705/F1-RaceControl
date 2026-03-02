from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class DriverState:
    """
    Deterministic per-driver race state derived from the canonical event log.

    All fields must be computable purely from events; no random or external
    state is allowed so that replays are reproducible.
    """

    driver_code: str

    # Basic race progress
    lap: int = 0
    position: Optional[int] = None

    # Tires / stint
    compound: Optional[str] = None
    stint: Optional[int] = None
    tire_age_laps: Optional[int] = None

    # Timing
    last_lap_time_s: Optional[float] = None
    last_lap_complete_time_s: Optional[float] = None
    gap_to_leader_s: Optional[float] = None

    # Aggregates
    total_pit_stops: int = 0


@dataclass
class RaceState:
    """
    Global race state at a particular point in the event stream.

    This is intended to be a pure data container with no behavior so that
    it can be safely deep-copied for snapshotting.
    """

    # Index of last-applied event in the event list (-1 = none applied yet)
    current_event_index: int = -1

    # Canonical race time in seconds at this state (typically the
    # event_time of the last-applied event, or 0.0 at the start).
    current_time_s: float = 0.0

    # Track status string (e.g. "GREEN", "YELLOW", "SC"), or None if unknown
    track_status: Optional[str] = None

    # Mapping from driver code (e.g. "VER") to per-driver state
    drivers: Dict[str, DriverState] = field(default_factory=dict)

    # Metadata
    total_events: int = 0


@dataclass
class RaceSnapshot:
    """
    Immutable snapshot of race state at a particular event index and time.

    The engine is responsible for creating these snapshots and restoring
    them when seeking; this class just carries structured data.
    """

    event_index: int
    time_s: float
    state: RaceState

