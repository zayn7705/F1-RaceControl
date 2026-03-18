"""
Snapshot I/O for saving race state to disk.

Saves state to snapshots/{race_id}/ with deterministic filenames.
"""

from __future__ import annotations

import json
from pathlib import Path

from .state import RaceState, state_to_dict


def save_snapshot(state: RaceState, race_id: str, base_dir: Path) -> Path:
    """
    Save race state to snapshots/{race_id}/snapshot_event{idx}_time{time}s.json.

    Args:
        state: Current race state to save
        race_id: Race identifier (used as subfolder name)
        base_dir: Base directory for snapshots (e.g., Path("snapshots"))

    Returns:
        Path to the written file
    """
    race_dir = base_dir / race_id
    race_dir.mkdir(parents=True, exist_ok=True)

    event_index = state.current_event_index
    event_time_s = state.current_time_s
    filename = f"snapshot_event{event_index}_time{event_time_s}s.json"
    filepath = race_dir / filename

    payload = {
        "race_id": race_id,
        "event_index": event_index,
        "event_time_s": event_time_s,
        "state": state_to_dict(state),
    }

    with filepath.open("w") as f:
        json.dump(payload, f, indent=2)

    return filepath
