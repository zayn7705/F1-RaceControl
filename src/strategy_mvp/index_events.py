from __future__ import annotations

import bisect
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


def load_events_jsonl(path: str | Path) -> List[Dict[str, Any]]:
    """Load canonical JSONL event list (one JSON object per line)."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Events file not found: {p}")
    events: List[Dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))
    return events


def _norm_status(raw: str) -> str:
    u = raw.strip().upper()
    if "VSC" in u or u == "4" or "VIRTUAL" in u:
        return "VSC"
    if "SAFETY" in u or u == "SC" or u == "2":
        return "SC"
    if "CLEAR" in u or u == "1" or u == "GREEN":
        return "GREEN"
    if "YELLOW" in u or u == "YELLOW":
        return "YELLOW"
    return u or "UNKNOWN"


@dataclass
class LapRecord:
    lap: int
    lap_time_s: float
    event_time: float
    compound: Optional[str] = None


@dataclass
class RaceIndex:
    """
    Precomputed index over canonical events for simulation.

    Rivals use historical lap times; track status is taken from the timeline.
    """

    laps_by_driver: Dict[str, Dict[int, LapRecord]]
    status_points: List[Tuple[float, str]]  # sorted by time, (event_time, normalized status)
    pit_durations_s: List[float]
    max_lap: int
    default_pit_duration_s: float
    drivers: List[str] = field(default_factory=list)

    def event_time_end_lap(self, driver: str, lap: int) -> Optional[float]:
        rec = self.laps_by_driver.get(driver, {}).get(lap)
        if rec is None:
            return None
        return rec.event_time

    def base_lap_time(self, driver: str, lap: int) -> Optional[float]:
        rec = self.laps_by_driver.get(driver, {}).get(lap)
        if rec is None:
            return None
        return rec.lap_time_s

    def status_at_time(self, t: float) -> str:
        if not self.status_points:
            return "GREEN"
        times = [p[0] for p in self.status_points]
        i = bisect.bisect_right(times, t) - 1
        if i < 0:
            return self.status_points[0][1]
        return self.status_points[i][1]

    def status_for_driver_lap(self, driver: str, lap: int) -> str:
        """Track status at end of this lap (lap_complete event time)."""
        t = self.event_time_end_lap(driver, lap)
        if t is None:
            return "GREEN"
        return self.status_at_time(t)

    def cumulative_historical_through_lap(self, driver: str, through_lap: int) -> float:
        """Sum of historical lap times for laps 1..through_lap inclusive."""
        per = self.laps_by_driver.get(driver)
        if not per:
            return 0.0
        total = 0.0
        last_time = 90.0
        for lap in range(1, through_lap + 1):
            r = per.get(lap)
            if r is not None and r.lap_time_s is not None and r.lap_time_s > 0:
                total += float(r.lap_time_s)
                last_time = float(r.lap_time_s)
            else:
                total += last_time
        return total

    def simulated_positions_at_lap(
        self,
        player: str,
        through_lap: int,
        player_cumulative_s: float,
    ) -> List[Tuple[str, float]]:
        """
        Return (driver_code, cumulative_time_s) sorted by time for counterfactual order.

        Player uses simulated cumulative time; others use historical sums through through_lap.
        """
        rows: List[Tuple[str, float]] = []
        for d in self.drivers:
            if d == player:
                rows.append((d, player_cumulative_s))
            else:
                rows.append((d, self.cumulative_historical_through_lap(d, through_lap)))
        rows.sort(key=lambda x: x[1])
        return rows


def build_race_index(events: Sequence[Dict[str, Any]]) -> RaceIndex:
    """Build RaceIndex from sorted canonical events."""
    laps_by_driver: Dict[str, Dict[int, LapRecord]] = {}
    status_points: List[Tuple[float, str]] = []
    pit_durations_s: List[float] = []

    for ev in events:
        et = ev.get("event_type")
        t = float(ev.get("event_time", 0.0))
        if et == "track_status":
            pl = ev.get("payload") or {}
            st = _norm_status(str(pl.get("status", "UNKNOWN")))
            status_points.append((t, st))
        elif et == "lap_complete":
            drv = ev.get("driver")
            lap = ev.get("lap")
            if not drv or lap is None:
                continue
            drv = str(drv)
            lap = int(lap)
            payload = ev.get("payload") or {}
            lt = payload.get("lap_time_s")
            if lt is None or float(lt) <= 0:
                continue
            comp = payload.get("compound")
            if comp is not None:
                comp = str(comp).upper()
            rec = LapRecord(
                lap=lap,
                lap_time_s=float(lt),
                event_time=t,
                compound=comp,
            )
            laps_by_driver.setdefault(drv, {})[lap] = rec
        elif et == "pit_stop":
            payload = ev.get("payload") or {}
            dur = payload.get("pit_duration_s")
            if dur is not None and float(dur) > 0:
                pit_durations_s.append(float(dur))

    status_points.sort(key=lambda x: x[0])

    drivers = sorted(laps_by_driver.keys())
    max_lap = 0
    for dm in laps_by_driver.values():
        if dm:
            max_lap = max(max_lap, max(dm.keys()))

    if pit_durations_s:
        pit_durations_s.sort()
        default_pit = pit_durations_s[len(pit_durations_s) // 2]
    else:
        default_pit = 22.0

    return RaceIndex(
        laps_by_driver=laps_by_driver,
        status_points=status_points,
        pit_durations_s=pit_durations_s,
        max_lap=max_lap,
        default_pit_duration_s=default_pit,
        drivers=drivers,
    )
