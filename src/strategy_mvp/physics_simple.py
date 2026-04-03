from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .index_events import RaceIndex


@dataclass(frozen=True)
class ModelParams:
    """Deterministic toy model — not physical realism, labeled honestly in UI."""

    compound_lap_delta_s: dict  # vs MEDIUM baseline
    degradation_s_per_stint_lap: float = 0.035
    sc_pit_loss_factor: float = 0.38  # multiply wall-clock pit loss under SC/VSC


DEFAULT_PARAMS = ModelParams(
    compound_lap_delta_s={"SOFT": -0.14, "MEDIUM": 0.0, "HARD": 0.24},
    degradation_s_per_stint_lap=0.035,
    sc_pit_loss_factor=0.38,
)


def normalize_compound(raw: str) -> Optional[str]:
    u = raw.strip().upper()
    if u in {"SOFT", "MEDIUM", "HARD"}:
        return u
    return None


def is_sc_period(status: str) -> bool:
    s = status.upper()
    return s in {"SC", "VSC"}


def modeled_lap_time_s(
    index: RaceIndex,
    driver: str,
    lap: int,
    compound: str,
    tire_age_laps: int,
    params: ModelParams = DEFAULT_PARAMS,
) -> float:
    """
    Lap time = historical baseline + compound delta + linear degradation in stint.
    """
    base = index.base_lap_time(driver, lap)
    if base is None or base <= 0:
        base = 90.0
    comp = normalize_compound(compound) or "MEDIUM"
    delta = float(params.compound_lap_delta_s.get(comp, 0.0))
    deg = params.degradation_s_per_stint_lap * max(0, tire_age_laps)
    return base + delta + deg


def pit_loss_duration_s(
    index: RaceIndex,
    track_status: str,
    params: ModelParams = DEFAULT_PARAMS,
) -> float:
    base = index.default_pit_duration_s
    if is_sc_period(track_status):
        return base * params.sc_pit_loss_factor
    return base
