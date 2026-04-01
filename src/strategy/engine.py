from __future__ import annotations

from dataclasses import asdict
from typing import Dict, List, Literal, Optional

from replay.state import RaceState

from .types import DriverRecommendation, PitWindowLabel, RecommendationLabel, SafetyCarTrigger


class StrategyEngine:
    """
    Deterministic, bounded-time heuristic strategy engine.

    Emits one recommendation per driver every `emit_every_laps` laps, and on
    safety-car / VSC deployment or end (track-status transitions) so triggers
    are not missed between periodic ticks.
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
        self._last_regular_emit_lap: Optional[int] = None
        self._prev_track_status: Optional[str] = None
        self._last_transition_emit_event_index: int = -1

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
            self._advance_track_memory(state)
            return None

        transition_kind = self._classify_track_transition(self._prev_track_status, state.track_status)
        emit_regular = (
            tick_lap % self.emit_every_laps == 0 and self._last_regular_emit_lap != tick_lap
        )
        emit_transition = transition_kind in {"deployment", "cleared"} and (
            state.current_event_index != self._last_transition_emit_event_index
        )

        if not emit_regular and not emit_transition:
            self._advance_track_memory(state)
            return None

        recs: List[DriverRecommendation] = []
        track_status = state.track_status
        time_s = float(state.current_time_s)
        row_trigger = self._row_safety_car_trigger(transition_kind, track_status, emit_transition)

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
            pit_window = self._pit_window(
                track_status=track_status,
                compound=d.compound,
                tire_age_laps=d.tire_age_laps,
            )

            recs.append(
                DriverRecommendation(
                    race_id=race_id,
                    time_s=time_s,
                    lap=tick_lap,
                    driver=d.driver_code,
                    recommendation=label,
                    pit_window=pit_window,
                    safety_car_trigger=row_trigger,
                    track_status=track_status,
                    compound=d.compound,
                    tire_age_laps=d.tire_age_laps,
                    position=d.position,
                    gap_to_leader_s=gap,
                    gap_delta_to_leader_s=gap_delta,
                    total_pit_stops=d.total_pit_stops,
                )
            )

        if emit_regular:
            self._last_regular_emit_lap = tick_lap
        if emit_transition:
            self._last_transition_emit_event_index = state.current_event_index

        self._advance_track_memory(state)
        return recs

    @staticmethod
    def to_json_dict(rec: DriverRecommendation) -> dict:
        d = asdict(rec)
        # Move feature fields under "features" for the JSONL log format
        features = {
            "pit_window": d.pop("pit_window"),
            "safety_car_trigger": d.pop("safety_car_trigger"),
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

    def _advance_track_memory(self, state: RaceState) -> None:
        self._update_gap_memory(state)
        self._prev_track_status = state.track_status

    def _update_gap_memory(self, state: RaceState) -> None:
        for d in state.drivers.values():
            if d.lap <= 0:
                continue
            if d.gap_to_leader_s is None:
                continue
            self._last_gap_to_leader[d.driver_code] = float(d.gap_to_leader_s)
            self._last_lap_seen[d.driver_code] = int(d.lap)

    @staticmethod
    def _is_sc_period(status: Optional[str]) -> bool:
        if status is None:
            return False
        return status.upper() in {"SC", "VSC"}

    @classmethod
    def _classify_track_transition(
        cls, prev: Optional[str], curr: Optional[str]
    ) -> Literal["none", "deployment", "cleared", "active"]:
        p_sc = cls._is_sc_period(prev)
        c_sc = cls._is_sc_period(curr)
        if not p_sc and c_sc:
            return "deployment"
        if p_sc and not c_sc:
            return "cleared"
        if c_sc:
            return "active"
        return "none"

    @classmethod
    def _row_safety_car_trigger(
        cls,
        transition_kind: Literal["none", "deployment", "cleared", "active"],
        track_status: Optional[str],
        emit_transition: bool,
    ) -> SafetyCarTrigger:
        if emit_transition and transition_kind == "deployment":
            return "deployment"
        if emit_transition and transition_kind == "cleared":
            return "cleared"
        if cls._is_sc_period(track_status):
            return "active"
        return "none"

    def _compound_stint_horizon(self, compound: Optional[str]) -> int:
        """Deterministic target lap age before pit; derived from max_tire_age_laps."""
        base = self.max_tire_age_laps
        if compound is None:
            return base
        c = compound.upper()
        if c == "SOFT":
            return max(1, base - 3)
        if c == "MEDIUM":
            return max(1, base)
        if c == "HARD":
            return base + 5
        return base

    def _pit_window(
        self,
        *,
        track_status: Optional[str],
        compound: Optional[str],
        tire_age_laps: Optional[int],
    ) -> PitWindowLabel:
        """
        Pit window heuristic: immediate vs opening vs hold.

        Under SC/VSC, pit loss is compressed — flag a cheap-stop window when tires are
        no longer brand-new.
        """
        if compound is None or tire_age_laps is None:
            return "hold"

        age = int(tire_age_laps)
        status = (track_status or "UNKNOWN").upper()

        if status in {"SC", "VSC"}:
            if age >= 3:
                return "immediate"
            return "opening"

        horizon = self._compound_stint_horizon(compound)
        if age >= horizon:
            return "immediate"
        if age >= max(0, horizon - 3):
            return "opening"
        return "hold"

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

