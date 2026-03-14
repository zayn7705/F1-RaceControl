from __future__ import annotations

import bisect
import copy
from dataclasses import replace
from typing import Any, Dict, List, Optional, Sequence

from .state import DriverState, RaceSnapshot, RaceState


class RaceStateEngine:
    """
    Deterministic race state engine driven by a canonical event list.

    The engine never mutates the underlying events or their ordering; it
    only walks the list in order, optionally using snapshots to seek.
    """

    def __init__(
        self,
        events: Sequence[Dict[str, Any]],
        snapshot_interval_events: int = 50,
    ) -> None:
        self._events: List[Dict[str, Any]] = list(events)
        self._state = RaceState(total_events=len(self._events))
        self._snapshot_interval = max(1, snapshot_interval_events)

        # Snapshots are kept sorted by event_index
        self._snapshots: List[RaceSnapshot] = []
        # Initial snapshot at index -1 / time 0.0
        self._create_snapshot()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def events(self) -> Sequence[Dict[str, Any]]:
        return self._events

    def reset(self) -> None:
        """Reset to the initial state (before first event)."""
        self._state = RaceState(total_events=len(self._events))
        self._snapshots = []
        self._create_snapshot()

    def get_state(self) -> RaceState:
        """
        Return a copy of the current race state.

        Callers should treat this as read-only; mutations will not affect
        the engine's internal state.
        """
        return copy.deepcopy(self._state)

    def apply_next_event(self) -> Optional[RaceState]:
        """
        Apply the next event in sequence.

        Returns the updated state, or None if there are no more events.
        """
        next_index = self._state.current_event_index + 1
        if next_index >= len(self._events):
            return None

        event = self._events[next_index]
        self._apply_event(event)
        self._state.current_event_index = next_index
        self._state.current_time_s = float(event.get("event_time", self._state.current_time_s))

        # Create snapshot periodically
        if next_index % self._snapshot_interval == 0:
            self._create_snapshot()

        return self.get_state()

    def apply_until_event_index(self, target_index: int) -> RaceState:
        """
        Apply events sequentially until reaching target_index (inclusive).

        If target_index is before the current index, a seek is performed
        using snapshots.
        """
        if target_index < -1 or target_index >= len(self._events):
            raise ValueError(f"target_index {target_index} out of range")

        if target_index <= self._state.current_event_index:
            # Seek backwards (or stay) via snapshots
            self.jump_to_event(target_index)
            return self.get_state()

        while self._state.current_event_index < target_index:
            if self.apply_next_event() is None:
                break

        return self.get_state()

    def apply_until_time(self, target_time_s: float) -> RaceState:
        """
        Apply events with event_time <= target_time_s.
        """
        if target_time_s < 0:
            target_time_s = 0.0

        # Find last event index satisfying event_time <= target_time_s
        times = [float(e.get("event_time", 0.0)) for e in self._events]
        target_index = -1
        for i, t in enumerate(times):
            if t <= target_time_s:
                target_index = i
            else:
                break

        return self.apply_until_event_index(target_index)

    def jump_to_event(self, target_index: int) -> RaceState:
        """
        Jump to the state at target_index using snapshots for efficiency.

        The resulting state is identical to sequentially applying events
        from the beginning up to target_index.
        """
        if target_index < -1 or target_index >= len(self._events):
            raise ValueError(f"target_index {target_index} out of range")

        if target_index == self._state.current_event_index:
            return self.get_state()

        # Find snapshot with largest event_index <= target_index
        snapshot_indexes = [s.event_index for s in self._snapshots]
        pos = bisect.bisect_right(snapshot_indexes, target_index) - 1
        if pos < 0:
            # Should not happen because we always keep an initial snapshot
            self.reset()
        else:
            snapshot = self._snapshots[pos]
            self._state = copy.deepcopy(snapshot.state)

        # Apply remaining events up to target_index
        while self._state.current_event_index < target_index:
            self.apply_next_event()

        return self.get_state()

    def jump_to_time(self, target_time_s: float) -> RaceState:
        """
        Jump to the state at a given race-relative time using snapshots.
        """
        if target_time_s < 0:
            target_time_s = 0.0

        last_event_time = self._events[-1]["event_time"] if self._events else 0.0
        if target_time_s > last_event_time:
            target_time_s = float(last_event_time)

        # Determine target index by scanning times (events are already sorted)
        times = [float(e.get("event_time", 0.0)) for e in self._events]
        target_index = -1
        for i, t in enumerate(times):
            if t <= target_time_s:
                target_index = i
            else:
                break

        return self.jump_to_event(target_index)

    def rewind(self, delta_s: float) -> RaceState:
        """Rewind backwards by delta_s seconds of race time."""
        if delta_s < 0:
            raise ValueError("delta_s must be non-negative")
        target_time = max(0.0, self._state.current_time_s - delta_s)
        return self.jump_to_time(target_time)

    def fast_forward(self, delta_s: float) -> RaceState:
        """Fast-forward forwards by delta_s seconds of race time."""
        if delta_s < 0:
            raise ValueError("delta_s must be non-negative")

        last_event_time = self._events[-1]["event_time"] if self._events else 0.0
        target_time = min(float(last_event_time), self._state.current_time_s + delta_s)
        return self.jump_to_time(target_time)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _create_snapshot(self) -> None:
        """Create a snapshot of the current state."""
        snapshot = RaceSnapshot(
            event_index=self._state.current_event_index,
            time_s=self._state.current_time_s,
            state=copy.deepcopy(self._state),
        )
        self._snapshots.append(snapshot)

    def _apply_event(self, event: Dict[str, Any]) -> None:
        event_type = event.get("event_type")
        if event_type == "lap_complete":
            self._apply_lap_complete(event)
        elif event_type == "pit_stop":
            self._apply_pit_stop(event)
        elif event_type == "track_status":
            self._apply_track_status(event)
        else:
            # Unknown events are ignored to keep engine robust but deterministic
            pass

    def _get_or_create_driver(self, driver_code: str) -> DriverState:
        if driver_code not in self._state.drivers:
            self._state.drivers[driver_code] = DriverState(driver_code=driver_code)
        return self._state.drivers[driver_code]

    def _apply_lap_complete(self, event: Dict[str, Any]) -> None:
        driver_code = event.get("driver")
        if not driver_code:
            return

        payload = event.get("payload", {}) or {}
        driver = self._get_or_create_driver(driver_code)

        # Update basic progress
        lap = event.get("lap")
        if isinstance(lap, int) and lap > 0:
            driver.lap = lap

        # Tires / stint
        compound = payload.get("compound")
        if compound is not None:
            driver.compound = compound

        stint = payload.get("stint")
        if stint is not None:
            driver.stint = stint

        tire_age = payload.get("tire_age_laps")
        if tire_age is not None:
            driver.tire_age_laps = tire_age

        tyre_life = payload.get("tyre_life")
        if tyre_life is not None:
            driver.tyre_life = float(tyre_life)

        # Timing
        event_time = event.get("event_time")
        if event_time is not None:
            driver.last_lap_complete_time_s = float(event_time)

        lap_time = payload.get("lap_time_s")
        if lap_time is not None:
            driver.last_lap_time_s = float(lap_time)

        # Position
        position = payload.get("position")
        if position is not None:
            driver.position = int(position)

        # After updating this driver's data, recompute gaps to leader
        self._recompute_gaps()

    def _apply_pit_stop(self, event: Dict[str, Any]) -> None:
        driver_code = event.get("driver")
        if not driver_code:
            return

        payload = event.get("payload", {}) or {}
        driver = self._get_or_create_driver(driver_code)

        driver.total_pit_stops += 1

        # Update stint and compound after the stop if provided
        stint = payload.get("stint")
        if stint is not None:
            driver.stint = stint

        compound_after = payload.get("compound_after")
        if compound_after is not None:
            driver.compound = compound_after

        # New stint: reset tire age until next lap_complete (which will set it from payload)
        if stint is not None:
            driver.tire_age_laps = 0

        # Pit events do not directly change lap or position here; those are
        # updated on subsequent lap_complete events.

    def _apply_track_status(self, event: Dict[str, Any]) -> None:
        payload = event.get("payload", {}) or {}
        status = payload.get("status")
        if status is not None:
            self._state.track_status = status

    def _recompute_gaps(self) -> None:
        if not self._state.drivers:
            return

        # Group by lap
        by_lap: Dict[int, List[DriverState]] = {}
        for d in self._state.drivers.values():
            if d.lap > 0 and d.last_lap_complete_time_s is not None:
                by_lap.setdefault(d.lap, []).append(d)

        # For each lap, compute gaps relative to the leader on that lap.
        # Iterate in sorted lap order for deterministic results.
        for lap, drivers in sorted(by_lap.items()):
            if not drivers:
                continue

            # Prefer leader with position == 1; break ties by time then driver_code for determinism
            leader_candidates = [d for d in drivers if d.position == 1]
            if leader_candidates:
                leader = min(
                    leader_candidates,
                    key=lambda d: (d.last_lap_complete_time_s or 0.0, d.driver_code),
                )
            else:
                leader = min(drivers, key=lambda d: (d.last_lap_complete_time_s or 0.0, d.driver_code))

            leader_time = leader.last_lap_complete_time_s or 0.0
            leader.gap_to_leader_s = 0.0

            for d in drivers:
                if d is leader:
                    continue
                if d.last_lap_complete_time_s is None:
                    d.gap_to_leader_s = None
                else:
                    d.gap_to_leader_s = max(0.0, d.last_lap_complete_time_s - leader_time)

