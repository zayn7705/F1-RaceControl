"""
Time utility functions for RaceControl
"""

from __future__ import annotations

import math
from typing import Iterable, Mapping, Optional


def to_optional_float(value) -> Optional[float]:
    """Convert a value to float, returning None for missing/invalid inputs."""
    if value is None:
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(converted) or math.isinf(converted):
        return None
    return converted


def safe_mean(values: Iterable[Optional[float]]) -> Optional[float]:
    """Return arithmetic mean over non-missing values, else None."""
    cleaned = [v for v in (to_optional_float(x) for x in values) if v is not None]
    if not cleaned:
        return None
    return sum(cleaned) / len(cleaned)


def extract_sector_times(
    lap_payload: Mapping[str, object],
    infer_single_missing: bool = False,
) -> dict:
    """
    Extract sector times in a strategy-safe way.

    If infer_single_missing is True and exactly one sector is missing while
    lap_time_s is available, infer the missing sector as:
        missing = lap_time_s - sum(known_sectors)
    Only non-negative inferred values are accepted.
    """
    sectors = [
        to_optional_float(lap_payload.get("sector1_time_s")),
        to_optional_float(lap_payload.get("sector2_time_s")),
        to_optional_float(lap_payload.get("sector3_time_s")),
    ]
    inferred = [False, False, False]

    if infer_single_missing:
        lap_time = to_optional_float(lap_payload.get("lap_time_s"))
        missing_count = sum(1 for s in sectors if s is None)
        if lap_time is not None and missing_count == 1:
            idx = sectors.index(None)
            known_sum = sum(s for s in sectors if s is not None)
            candidate = lap_time - known_sum
            if candidate >= 0:
                sectors[idx] = candidate
                inferred[idx] = True

    return {
        "sector1_time_s": sectors[0],
        "sector2_time_s": sectors[1],
        "sector3_time_s": sectors[2],
        "sector_count_available": sum(1 for s in sectors if s is not None),
        "is_complete": all(s is not None for s in sectors),
        "inferred_flags": inferred,
    }