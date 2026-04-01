"""
Interactive counterfactual strategy MVP (Hungary 2022 race, dry compounds).

Truth data comes from canonical JSONL; player timeline is simulated with a simple model.
"""

from .benchmark import compute_benchmark
from .candidates import StrategyPlan, enumerate_candidates
from .constants import DEFAULT_HUNGARY_2022_JSONL
from .index_events import RaceIndex, build_race_index, load_events_jsonl
from .player_state import PitRecord, PlayerState
from .simulator import apply_player_step, run_fixed_plan_total_time

__all__ = [
    "RaceIndex",
    "build_race_index",
    "load_events_jsonl",
    "PlayerState",
    "PitRecord",
    "StrategyPlan",
    "enumerate_candidates",
    "compute_benchmark",
    "run_fixed_plan_total_time",
    "apply_player_step",
    "DEFAULT_HUNGARY_2022_JSONL",
]
