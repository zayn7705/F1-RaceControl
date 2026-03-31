"""
Strategy package for RaceControl.

Contains deterministic, bounded-time strategy recommendation logic that consumes
RaceState snapshots.
"""

from .engine import StrategyEngine
from .types import DriverRecommendation

__all__ = ["StrategyEngine", "DriverRecommendation"]

