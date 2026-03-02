"""
FastF1 data ingestion module for RaceControl
"""

from .fastf1_loader import load_race
from .event_builder import build_events

__all__ = ['load_race', 'build_events']
