from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


@dataclass(frozen=True)
class StrategyPlan:
    """Fixed pit schedule for benchmark search (dry compounds only)."""

    name: str
    stint_compounds: List[str]  # length = len(pit_before_laps) + 1
    pit_before_laps: List[int]  # pit immediately before starting this lap number


def enumerate_candidates(max_lap: int) -> List[StrategyPlan]:
    """Finite set of strategies to search — coarse grid, bounded count."""
    if max_lap < 5:
        return [
            StrategyPlan("0-stop MEDIUM", ["MEDIUM"], []),
        ]

    out: List[StrategyPlan] = []
    for c in ("MEDIUM", "HARD"):
        out.append(StrategyPlan(f"0-stop {c}", [c], []))

    step = max(3, (max_lap - 15) // 8)
    for p in range(14, max(15, max_lap - 2), step):
        for a, b in (("SOFT", "MEDIUM"), ("MEDIUM", "HARD"), ("SOFT", "HARD")):
            out.append(StrategyPlan(f"1-stop pit@{p} {a}->{b}", [a, b], [p]))

    # 2-stop: sparse
    mid = max_lap // 2
    for p1 in range(12, mid, 7):
        for p2 in range(p1 + 8, max_lap - 2, 7):
            if p2 >= max_lap:
                continue
            out.append(
                StrategyPlan(
                    f"2-stop pit@{p1},{p2} SOFT/MED/HARD",
                    ["SOFT", "MEDIUM", "HARD"],
                    [p1, p2],
                )
            )

    return out


def model_scores_from_times(times: List[float]) -> List[int]:
    """
    Map lower time -> higher 0–100 score (model ranking, not probability).
    """
    if not times:
        return []
    t_min = min(times)
    t_max = max(times)
    span = max(t_max - t_min, 1e-6)
    scores = []
    for t in times:
        # lower time => higher score
        s = 100.0 * (1.0 - (t - t_min) / span)
        scores.append(int(round(max(0.0, min(100.0, s)))))
    return scores


def rank_plans_with_scores(
    plans: List[StrategyPlan], times: List[float]
) -> List[Tuple[StrategyPlan, float, int, str]]:
    """Return sorted (plan, time_s, score_0_100, rationale)."""
    scores = model_scores_from_times(times)
    rows = list(zip(plans, times, scores))
    rows.sort(key=lambda x: x[1])
    ranked: List[Tuple[StrategyPlan, float, int, str]] = []
    for i, (pl, tm, sc) in enumerate(rows):
        rationale = (
            f"Model time {tm:.2f}s; {len(pl.pit_before_laps)} stop(s); "
            f"stints {' -> '.join(pl.stint_compounds)}"
        )
        if i == 0:
            rationale += " (fastest in searched set)"
        ranked.append((pl, tm, sc, rationale))
    return ranked
