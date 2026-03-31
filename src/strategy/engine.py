from __future__ import annotations

from dataclasses import asdict
from typing import Dict, List, Optional, Tuple

from replay.state import RaceState

from .types import DriverRecommendation, RecommendationLabel


class StrategyEngine:
    """
    Deterministic, bounded-time heuristic strategy engine.

    Emits one recommendation per driver every `emit_every_laps` laps.
    """

    def __init__(
        self,
        emit_every_laps: int = 5,
        max_tire_age_laps: int = 15,
        gap_delta_cutoff_s: float = 0.2,
        max_pit_stops_bias: int = 3,
    ) -> None:
        self.emit_every_laps = max(1, emit_every_laps)
        self.max_tire_age_laps = max(0, max_tire_age_laps)
        self.gap_delta_cutoff_s = max(0.0, gap_delta_cutoff_s)
        self.max_pit_stops_bias = max(0, max_pit_stops_bias)

        self._last_gap_to_leader: Dict[str, float] = {}
        self._last_lap_seen: Dict[str, int] = {}
        self._last_emitted_lap: Optional[int] = None

    def observe(self, state: RaceState, race_id: str) -> Optional[List[DriverRecommendation]]:
        """
        Observe the latest RaceState and (optionally) emit recommendations.

        Returns:
            List of DriverRecommendation if emitted at this tick, else None.
        """
        if not state.drivers:
            return None

        tick_lap = max(d.lap for d in state.drivers.values())
        if tick_lap <= 0:
            return None

        if tick_lap % self.emit_every_laps != 0:
            self._update_gap_memory(state)
            return None

        if self._last_emitted_lap == tick_lap:
            self._update_gap_memory(state)
            return None

        recs: List[DriverRecommendation] = []
        track_status = state.track_status
        time_s = float(state.current_time_s)

        # Deterministic ordering: position then driver_code
        drivers_sorted = sorted(
            state.drivers.values(),
            key=lambda d: (d.position if d.position is not None else 999, d.driver_code),
        )

        for d in drivers_sorted:
            gap = d.gap_to_leader_s
            gap_delta = self._compute_gap_delta(d.driver_code, d.lap, gap)

            label = self._recommend_label(
                track_status=track_status,
                compound=d.compound,
                tire_age_laps=d.tire_age_laps,
                position=d.position,
                gap_to_leader_s=gap,
                gap_delta_to_leader_s=gap_delta,
                total_pit_stops=d.total_pit_stops,
            )

            recs.append(
                DriverRecommendation(
                    race_id=race_id,
                    time_s=time_s,
                    lap=tick_lap,
                    driver=d.driver_code,
                    recommendation=label,
                    track_status=track_status,
                    compound=d.compound,
                    tire_age_laps=d.tire_age_laps,
                    position=d.position,
                    gap_to_leader_s=gap,
                    gap_delta_to_leader_s=gap_delta,
                    total_pit_stops=d.total_pit_stops,
                )
            )

        self._last_emitted_lap = tick_lap
        self._update_gap_memory(state)
        return recs

    @staticmethod
    def to_json_dict(rec: DriverRecommendation) -> dict:
        d = asdict(rec)
        # Move feature fields under "features" for the JSONL log format
        features = {
            "track_status": d.pop("track_status"),
            "compound": d.pop("compound"),
            "tire_age_laps": d.pop("tire_age_laps"),
            "position": d.pop("position"),
            "gap_to_leader_s": d.pop("gap_to_leader_s"),
            "gap_delta_to_leader_s": d.pop("gap_delta_to_leader_s"),
            "total_pit_stops": d.pop("total_pit_stops"),
        }
        d["features"] = features
        return d

    def _update_gap_memory(self, state: RaceState) -> None:
        for d in state.drivers.values():
            if d.lap <= 0:
                continue
            if d.gap_to_leader_s is None:
                continue
            self._last_gap_to_leader[d.driver_code] = float(d.gap_to_leader_s)
            self._last_lap_seen[d.driver_code] = int(d.lap)

    def _compute_gap_delta(self, driver: str, lap: int, gap_to_leader_s: Optional[float]) -> Optional[float]:
        if gap_to_leader_s is None:
            return None
        if driver not in self._last_gap_to_leader or driver not in self._last_lap_seen:
            return None
        if lap <= self._last_lap_seen[driver]:
            return None
        return float(gap_to_leader_s) - float(self._last_gap_to_leader[driver])

    def _recommend_label(
        self,
        *,
        track_status: Optional[str],
        compound: Optional[str],
        tire_age_laps: Optional[int],
        position: Optional[int],
        gap_to_leader_s: Optional[float],
        gap_delta_to_leader_s: Optional[float],
        total_pit_stops: int,
    ) -> RecommendationLabel:
        # Guardrails: if core features missing, be conservative.
        if position is None or compound is None or tire_age_laps is None:
            return "other"

        # Track status normalization
        status = (track_status or "UNKNOWN").upper()
        comp = compound.upper()

        tire_age = int(tire_age_laps)
        pit_stops = int(total_pit_stops)

        # Base scores
        undercut = 0.0
        overcut = 0.0

        # Safety/flag bias: pit loss reduced, so pitting earlier is favored.
        if status in {"SC", "VSC"}:
            undercut += 1.0
            # If tires are already old, favor taking the \"cheap\" stop.
            if tire_age >= self.max_tire_age_laps:
                undercut += 1.0
            # If already pitted many times, reduce undercut incentive.
            if pit_stops >= self.max_pit_stops_bias:
                undercut -= 0.5

        # Tire degradation proxy by compound and age
        if comp == "SOFT":
            age_pressure = tire_age - (self.max_tire_age_laps - 3)
        elif comp == "MEDIUM":
            age_pressure = tire_age - (self.max_tire_age_laps - 1)
        else:
            # HARD/UNKNOWN -> less degradation pressure
            age_pressure = tire_age - self.max_tire_age_laps

        if age_pressure >= 0:
            undercut += 0.8 + 0.05 * age_pressure
        else:
            overcut += 0.4

        # Traffic proxy: if not leading, undercut becomes more attractive.
        if position > 1:
            undercut += 0.3
        else:
            overcut += 0.3

        # Gap trend: worsening gap -> undercut; improving -> overcut.
        if gap_delta_to_leader_s is not None:
            if gap_delta_to_leader_s >= self.gap_delta_cutoff_s:
                undercut += 0.7
            elif gap_delta_to_leader_s <= -self.gap_delta_cutoff_s:
                overcut += 0.7

        # If gap is tiny, avoid strong calls (uncertainty), unless SC/VSC.
        if gap_to_leader_s is not None and gap_to_leader_s < 1.0 and status not in {"SC", "VSC"}:
            undercut -= 0.2
            overcut -= 0.2

        if undercut >= overcut + 0.3:
            return "undercut"
        if overcut >= undercut + 0.3:
            return "overcut"
        return "other"

