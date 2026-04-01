from __future__ import annotations

from typing import List, Tuple

from .index_events import RaceIndex
from .physics_simple import DEFAULT_PARAMS, ModelParams, is_sc_period, modeled_lap_time_s
from .player_state import PlayerState


def lap_advice(
    index: RaceIndex,
    state: PlayerState,
    params: ModelParams = DEFAULT_PARAMS,
) -> str:
    """
    Short deterministic hint for the next lap (bounded, no ML).
    """
    lap = state.current_lap
    if lap > index.max_lap:
        return "Race finished in the model."

    drv = state.controlled_driver
    status = index.status_for_driver_lap(drv, lap - 1) if lap > 1 else index.status_at_time(0.0)
    sc = is_sc_period(status)

    stay_out_next = modeled_lap_time_s(
        index, drv, lap, state.compound, state.tire_age_laps, params
    )
    soft_next = modeled_lap_time_s(index, drv, lap, "SOFT", 0, params)

    hints: List[str] = []
    if sc:
        hints.append(
            "Caution period: pit lane loss is reduced in this model — a stop may be attractive if you need fresh rubber."
        )
    if state.tire_age_laps >= 18 and not sc:
        hints.append("Tire age is high — consider a stop soon if pace drops vs your targets.")
    if soft_next + 0.05 < stay_out_next:
        hints.append("Model suggests SOFT (fresh) would be quicker this lap than staying on current compound.")

    if not hints:
        hints.append(
            f"Next lap model pace on {state.compound} ~{stay_out_next:.2f}s (tire age {state.tire_age_laps})."
        )

    return " ".join(hints)


def compare_pit_vs_stay(
    index: RaceIndex,
    state: PlayerState,
    pit_compound: str,
    params: ModelParams = DEFAULT_PARAMS,
) -> Tuple[float, float]:
    """Return (modeled lap time if stay, modeled lap time if pit to compound with fresh tires)."""
    lap = state.current_lap
    stay = modeled_lap_time_s(
        index, state.controlled_driver, lap, state.compound, state.tire_age_laps, params
    )
    fresh = modeled_lap_time_s(
        index, state.controlled_driver, lap, pit_compound, 0, params
    )
    return stay, fresh
