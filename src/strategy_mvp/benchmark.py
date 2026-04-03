from __future__ import annotations

from typing import List, Tuple

from .candidates import StrategyPlan, enumerate_candidates, rank_plans_with_scores
from .index_events import RaceIndex
from .physics_simple import DEFAULT_PARAMS, ModelParams
from .simulator import run_fixed_plan_total_time


def compute_benchmark(
    index: RaceIndex,
    driver: str,
    params: ModelParams = DEFAULT_PARAMS,
) -> Tuple[StrategyPlan, float, List[Tuple[StrategyPlan, float, int, str]]]:
    """
    Best strategy among enumerated candidates under the same simple model.

    Returns (best_plan, best_time_s, full_ranked_list).
    """
    plans = enumerate_candidates(index.max_lap)
    times: List[float] = []
    for p in plans:
        times.append(run_fixed_plan_total_time(index, driver, p, params))
    ranked = rank_plans_with_scores(plans, times)
    best_plan, best_t, _, _ = ranked[0]
    return best_plan, best_t, ranked
