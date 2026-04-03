from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

RecommendationLabel = Literal["undercut", "overcut", "other"]
PitWindowLabel = Literal["immediate", "opening", "hold"]
SafetyCarTrigger = Literal["none", "deployment", "cleared", "active"]


@dataclass(frozen=True)
class DriverRecommendation:
    race_id: str
    time_s: float
    lap: int
    driver: str
    recommendation: RecommendationLabel
    pit_window: PitWindowLabel
    safety_car_trigger: SafetyCarTrigger
    track_status: Optional[str]
    compound: Optional[str]
    tire_age_laps: Optional[int]
    position: Optional[int]
    gap_to_leader_s: Optional[float]
    gap_delta_to_leader_s: Optional[float]
    total_pit_stops: int

