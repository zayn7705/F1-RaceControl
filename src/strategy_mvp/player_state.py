from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal, Optional

DryCompound = Literal["SOFT", "MEDIUM", "HARD"]


@dataclass
class PitRecord:
    """One pit stop in the player's counterfactual run."""

    before_lap: int
    """Pit applied immediately before completing this race lap (lap timer includes this lap)."""

    compound_after: str
    duration_s: float
    track_status: str


@dataclass
class PlayerState:
    controlled_driver: str
    current_lap: int
    compound: str
    tire_age_laps: int
    cumulative_time_s: float
    pit_stops_used: int
    pit_history: List[PitRecord] = field(default_factory=list)
    intended_plan_name: str = ""

    def copy_light(self) -> "PlayerState":
        return PlayerState(
            controlled_driver=self.controlled_driver,
            current_lap=self.current_lap,
            compound=self.compound,
            tire_age_laps=self.tire_age_laps,
            cumulative_time_s=self.cumulative_time_s,
            pit_stops_used=self.pit_stops_used,
            pit_history=list(self.pit_history),
            intended_plan_name=self.intended_plan_name,
        )
