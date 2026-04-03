from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .engine import StrategyEngine
from .types import DriverRecommendation


class StrategyJsonlLogger:
    """
    Append-only JSONL logger for strategy recommendations.

    Writes to: data/strategy_recs_{race_id}.jsonl
    """

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir

    def append(self, race_id: str, recs: Iterable[DriverRecommendation]) -> Path:
        self._base_dir.mkdir(parents=True, exist_ok=True)
        path = self._base_dir / f"strategy_recs_{race_id}.jsonl"

        with path.open("a") as f:
            for rec in recs:
                f.write(json.dumps(StrategyEngine.to_json_dict(rec)) + "\n")

        return path

