from __future__ import annotations

from typing import Optional, Tuple

from .candidates import StrategyPlan
from .index_events import RaceIndex
from .physics_simple import DEFAULT_PARAMS, ModelParams, modeled_lap_time_s, pit_loss_duration_s
from .player_state import PitRecord, PlayerState


def run_fixed_plan_total_time(
    index: RaceIndex,
    driver: str,
    plan: StrategyPlan,
    params: ModelParams = DEFAULT_PARAMS,
) -> float:
    """Deterministic full-race time for a fixed pit schedule (benchmark search)."""
    if not plan.stint_compounds:
        raise ValueError("plan must have stint compounds")
    expected_stints = len(plan.pit_before_laps) + 1
    if len(plan.stint_compounds) != expected_stints:
        raise ValueError("stint_compounds length must match pit_before_laps + 1")

    compound = plan.stint_compounds[0]
    tire_age = 0
    cum = 0.0
    pit_event = 0
    stint_index = 0

    for lap in range(1, index.max_lap + 1):
        if (
            pit_event < len(plan.pit_before_laps)
            and lap == plan.pit_before_laps[pit_event]
        ):
            if lap > 1:
                status = index.status_for_driver_lap(driver, lap - 1)
            else:
                status = index.status_at_time(0.0)
            cum += pit_loss_duration_s(index, status, params)
            stint_index += 1
            compound = plan.stint_compounds[stint_index]
            tire_age = 0
            pit_event += 1

        cum += modeled_lap_time_s(index, driver, lap, compound, tire_age, params)
        tire_age += 1

    return cum


def apply_player_step(
    index: RaceIndex,
    state: PlayerState,
    pit_to: Optional[str],
    params: ModelParams = DEFAULT_PARAMS,
) -> PlayerState:
    """
    Complete one race lap: optional pit before the lap, then lap time.

    Pit applies before `current_lap` if requested (fresh tires for this lap).
    """
    lap = state.current_lap
    if lap > index.max_lap:
        return state

    compound = state.compound
    tire_age = state.tire_age_laps
    cum = state.cumulative_time_s
    pits = state.pit_stops_used
    history = list(state.pit_history)

    if pit_to is not None:
        if lap > 1:
            status = index.status_for_driver_lap(state.controlled_driver, lap - 1)
        else:
            status = index.status_at_time(0.0)
        loss = pit_loss_duration_s(index, status, params)
        cum += loss
        compound = pit_to.upper()
        tire_age = 0
        pits += 1
        history.append(
            PitRecord(
                before_lap=lap,
                compound_after=compound,
                duration_s=loss,
                track_status=status,
            )
        )

    cum += modeled_lap_time_s(
        index, state.controlled_driver, lap, compound, tire_age, params
    )
    tire_age += 1

    return PlayerState(
        controlled_driver=state.controlled_driver,
        current_lap=lap + 1,
        compound=compound,
        tire_age_laps=tire_age,
        cumulative_time_s=cum,
        pit_stops_used=pits,
        pit_history=history,
        intended_plan_name=state.intended_plan_name,
    )


def simulated_position(
    index: RaceIndex, player: str, through_lap: int, player_cumulative_s: float
) -> Tuple[int, int]:
    """Return (position, field_size) with 1 = leader. Uses counterfactual ordering."""
    order = index.simulated_positions_at_lap(player, through_lap, player_cumulative_s)
    for i, (code, _) in enumerate(order):
        if code == player:
            return i + 1, len(order)
    return len(order), len(order)
