# AI Agent Instructions for RaceControl Project

You are an AI assistant helping with the **RaceControl** project: a Real-Time Formula 1 Strategy and Pit Decision Engine.

## Project Context

**Project Goal**: Build a software system that replays past F1 races as real-time event streams and generates strategy recommendations in real time.

**Project Status**:

- ✅ **Checkpoint 1 (CP1)**: Complete - Project proposal, repo setup, architecture design
- ✅ **Checkpoint 2 (CP2)**: Complete - Ingestion + Replay Engine working
- ✅ **Checkpoint 3 (CP3)**: Complete - Race state engine, snapshots, deterministic validation
- ✅ **Checkpoint 4 (CP4)**: Complete - Replay-integrated strategy engine (pit window, undercut/overcut, SC triggers, JSONL during replay)
- ⏳ **Checkpoint 5 (CP5)**: TODO - Reliability, Metrics, Demo

**In progress / exploratory**:

- **Hungary 2022 what-if prototype** (`src/strategy_mvp/`, `scripts/strategy_mvp_cli.py`): counterfactual pit/stint simulator and model benchmark—**scope and UX still evolving** (see README). Not part of the core deterministic replay contract.

**Current Capabilities**:

- Load historical F1 race data from FastF1 (2018+)
- Normalize events into canonical JSONL format
- Replay races with configurable speed control (1x, 5x, 20x)
- Maintain deterministic race state (positions, gaps, tires, lap times)
- Capture and save race state snapshots to disk via the `snapshot` CLI command
- Strategy recommendations during replay + optional **Rich strategy dashboard** (`scripts/replay_strategy_ui.py`)

**Next Milestones**:

- CP5: Fault tolerance, performance metrics, demo interface
- Continue exploring the Hungary what-if line (model, commands, honesty of labels)

---

## Your Role as AI Assistant

When helping with this project:

1. **Maintain Determinism**: All state evolution must be deterministic (same events → same state)
2. **Follow Schema**: Always validate against `schemas/event_schema.json`
3. **Test Changes**: Run test suite after modifications
4. **Preserve Patterns**: Follow existing code patterns in `src/ingest/` and `src/replay/`
5. **Handle Missing Data**: Use `src.utils.time_utils` for None-safe operations

---

## Project Structure

```
src/
├── ingest/              # CP2: FastF1 → normalized events ✅
│   ├── fastf1_loader.py
│   └── event_builder.py
├── replay/              # CP2+: deterministic state ✅
│   ├── engine.py
│   ├── controller.py
│   └── state.py
├── strategy/            # CP4: heuristic strategy + JSONL logger ✅
│   └── engine.py
├── strategy_mvp/        # Hungary what-if explorer (in progress / exploratory)
│   └── …
└── utils/
    └── time_utils.py

scripts/
├── export_events.py
├── replay_cli.py
├── replay_strategy_ui.py   # Terminal dashboard: state + strategy (Rich)
├── strategy_mvp_cli.py     # Hungary counterfactual prototype CLI
└── hello_world.py

schemas/
├── event_schema.json
└── examples/

tests/
```

See `README.md` for commands and how the what-if prototype differs from replay.

---

## Quick Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Verify installation
python scripts/hello_world.py  # Should print success message
```

**Key Dependencies**: `fastf1`, `pandas`, `jsonschema`, `pytest`, `rich` (for `replay_strategy_ui.py`)

---

## Core Workflows

### Workflow 1: Export and Replay (CP2 Complete ✅)

```bash
# Export events
python scripts/export_events.py --year 2022 --gp Hungary --session R --out data/hungary_2022.jsonl

# Replay with speed control
python scripts/replay_cli.py --events data/hungary_2022.jsonl --initial-speed 5.0
```

**Replay Commands**: `play`, `pause`, `speed 20`, `status`, `step 10`, `quit`
**Snapshot Command**: `snapshot` or `snapshot <seconds>` to persist state under `snapshots/{race_id}/`

### Workflow 2: Programmatic Usage

```python
from src.ingest import load_race, build_events
from src.replay import RaceStateEngine

# Load and normalize
raw = load_race(2022, "Hungary", "R")
events = build_events(raw)  # Returns List[dict]

# Process events
engine = RaceStateEngine(events)
state = engine.apply_next_event()  # Returns RaceState
```

---

## Event Schema (Critical Reference)

**Location**: `schemas/event_schema.json`

**Event Structure**:

```python
{
    "seq": int,                    # Monotonic: 0, 1, 2, ...
    "event_time": float,           # Seconds since race start
    "event_type": str,             # "lap_complete" | "pit_stop" | "track_status"
    "driver": str | None,          # "VER" or null
    "lap": int | None,             # Lap number or null
    "payload": dict                # Event-specific fields
}
```

**Event Types**:

1. **lap_complete** payload:
  - `lap_time_s`, `sector1_time_s`, `sector2_time_s`, `sector3_time_s`
  - `compound`, `stint`, `tire_age_laps`, `tyre_life`, `position`
2. **pit_stop** payload:
  - `pit_in_time_s`, `pit_out_time_s`, `pit_duration_s`
  - `stint`, `compound_after`
3. **track_status** payload:
  - `status`: "GREEN" | "YELLOW" | "VSC" | "SC"
  - `source`: "fastf1_track_status"

**Validation**: Always use `jsonschema.validate(instance=event, schema=schema)`

---

## Key APIs

### `load_race(year: int, gp: str, session_type: str = "R") -> dict`

Loads race data from FastF1. Auto-creates cache.

**Returns**: `{"session": FastF1Session, "laps": DataFrame, "timing_data": ...}`  
**Raises**: `ValueError` if race not found or year < 2018

### `build_events(raw_data: dict) -> List[dict]`

Normalizes FastF1 data to canonical events. Sorts by time, assigns `seq`.

**Returns**: Sorted list of event dicts

### `RaceStateEngine(events: List[dict], snapshot_interval_events: int = 50)`

Deterministic state engine.

**Methods**:

- `apply_next_event() -> RaceState | None`
- `get_state() -> RaceState` (read-only copy)
- `jump_to_time(time_s: float) -> RaceState`

### `ReplayController(events: List[dict], initial_speed: float = 1.0)`

Replay with speed control.

**Methods**:

- `play()`, `pause()`, `set_speed(speed)`, `step(n=1)`, `stop()`

---

## Testing

```bash
# Schema validation
python tests/test_event_schema_examples.py

# State engine
python tests/test_race_state_engine.py

# Time utilities
python -m pytest tests/test_time_utils.py -v

# CP2 completion
python tests/test_cp2_completion.py
```

**Expected**: All tests pass. Smoke test may skip if cache not warm (acceptable).

---

## Implementation Guidelines

### Determinism Requirements

- **Same events → same state**: RaceStateEngine must be fully deterministic
- **Event ordering**: Sorted by `(event_time, type_priority, driver, lap)`
- **Sequence numbers**: Assigned after sorting (0, 1, 2, ...)
- **No randomness**: Never use random values in state computation

### Missing Data Handling

- **Sector times**: May be `None` on lap 1 (expected). Use `src.utils.time_utils.extract_sector_times()`
- **Pit durations**: Properly extracted (fixed in recent commit)
- **Track status**: Extracted from `session.track_status` DataFrame

### State Immutability

- `RaceStateEngine.get_state()` returns **deep copy** - safe to modify
- Engine internal state never mutated by external code

### Thread Safety

- `ReplayController` uses locks for thread-safe playback
- Background thread handles timing; main thread handles commands

---

## Common Tasks

### Task: Add New Event Type

1. Update `schemas/event_schema.json` - add to `oneOf` in payload
2. Update `src/ingest/event_builder.py` - add `_build_*_events()` function
3. Update `src/replay/engine.py` - add `_apply_*()` method
4. Add example in `schemas/examples/`
5. Update tests
6. Validate: `python tests/test_event_schema_examples.py`

### Task: Debug Event Processing

```python
from src.ingest import load_race, build_events
from collections import Counter

raw = load_race(2022, "Hungary", "R")
events = build_events(raw)

print(f"Total: {len(events)}")
print(f"Types: {Counter(e['event_type'] for e in events)}")
print(f"Event 100: {events[100]}")
```

### Task: Validate Schema

```python
import json
import jsonschema

schema = json.load(open('schemas/event_schema.json'))
event = json.load(open('schemas/examples/lap_complete.json'))
jsonschema.validate(instance=event, schema=schema)
```

---

## Troubleshooting


| Problem                          | Solution                                            |
| -------------------------------- | --------------------------------------------------- |
| `ModuleNotFoundError: fastf1`    | `pip install -r requirements.txt`                   |
| `Cache directory does not exist` | Auto-created, or `mkdir -p cache`                   |
| `Failed to load race data`       | Check year >= 2018, verify GP name, ensure internet |
| `No events loaded`               | Verify export script ran, check JSONL exists        |
| Tests skip "cache not warm"      | Run export once to warm cache                       |


---

## File Locations


| Component         | File                          |
| ----------------- | ----------------------------- |
| FastF1 loader     | `src/ingest/fastf1_loader.py` |
| Event builder     | `src/ingest/event_builder.py` |
| Replay engine     | `src/replay/engine.py`        |
| Replay controller | `src/replay/controller.py`    |
| State definitions | `src/replay/state.py`         |
| Event schema      | `schemas/event_schema.json`   |
| Export script     | `scripts/export_events.py`    |
| Replay CLI        | `scripts/replay_cli.py`       |
| Strategy engine   | `src/strategy/engine.py`      |
| Strategy UI       | `scripts/replay_strategy_ui.py` |
| Hungary what-if   | `src/strategy_mvp/`, `scripts/strategy_mvp_cli.py` |
| Time utilities    | `src/utils/time_utils.py`     |


---

## Checkpoint Status

### ✅ CP1: Project Proposal + Repo Setup (Complete)

- GitHub repo with file layout
- Architecture documentation
- Event schema definition
- Milestone plan

### ✅ CP2: Ingestion + Replay Engine (Complete)

- FastF1 loader + event normalization
- Replay engine with speed control
- CLI runner
- **Success**: Replay of one race working with speed control ✅

### ✅ CP3: Race State Engine (Complete)

**Goal**: Enhanced state updates + snapshotting + validation  
**Success Criteria**: Same race run twice produces identical final state

**Tasks**:

- Implement state updates for all drivers ✅ (lap_complete: lap, position, compound, stint, tire_age_laps, tyre_life, last_lap_time_s, last_lap_complete_time_s, gap_to_leader; pit_stop: total_pit_stops, stint, compound_after, tire_age_laps reset; track_status: global)
- Implement snapshotting + validation scripts ✅ (snapshot_io)
- Add deterministic replay validation ✅ (`test_same_final_state_after_two_full_runs`, `test_full_replay_versus_jump_to_end`)

### ✅ CP4: Strategy Decision Engine (Complete)

**Goal**: Generate strategy recommendations during replay  
**Success Criteria**: Strategy outputs produced during replay

**Tasks**:

- Pit window recommendation logic (`pit_window`: immediate / opening / hold)
- Undercut/overcut evaluation model (heuristic scores)
- Safety car strategy triggers (deployment / cleared / active on periodic ticks; extra emit on SC/VSC transitions)
- Time-bounded simulation (deterministic heuristic in `src/strategy/engine.py`)

**Exploratory (not required for CP4 closure)**:

- **Hungary 2022 what-if** (`src/strategy_mvp/`, `scripts/strategy_mvp_cli.py`): counterfactual simulator + benchmark search—**in progress** for design and teaching; see `README.md` and `docs/milestone_plan.md`.

### ⏳ CP5: Reliability + Metrics + Demo (TODO)

**Goal**: Full race demo with recovery + performance results  
**Success Criteria**: Full race demo + recovery + performance results

**Tasks**:

- Checkpointing/recovery + fault injection
- Latency and throughput instrumentation
- Performance report (p50/p95 metrics)
- Demo polish

---

## When User Asks for Help

### If user says "help me with RaceControl":

1. Read this file to understand project structure
2. Check `schemas/event_schema.json` for event format
3. Run `python tests/test_event_schema_examples.py` to verify setup
4. Ask what they want to do (add feature, fix bug, work on CP3/4/5)

### If user says "implement X":

1. Understand X in context of existing codebase
2. Check if schema needs updates
3. Follow patterns in `src/ingest/` or `src/replay/`
4. Maintain determinism and test coverage
5. Update tests if needed

### If user says "help me with CP3/CP4/CP5":

1. Review checkpoint requirements above
2. Check what's already implemented
3. Plan implementation following existing patterns
4. Maintain backward compatibility
5. Add tests for new features

---

## Important Notes

- **Python**: 3.8+ (tested with 3.13)
- **Cache**: `cache/` (gitignored, auto-created)
- **Data**: `data/*.jsonl` (gitignored)
- **Determinism is critical**: Same events must produce same state
- **Schema is authoritative**: Always validate against `schemas/event_schema.json`
- **CP2–CP4 core is complete**: Ingestion, replay, state, and replay-integrated strategy. **CP5** is next. The **Hungary what-if** prototype is optional exploratory work—see README.

---

## Additional Context

**Project Proposal Summary**:

- Focus: Real-time F1 strategy with deterministic decision system
- Goal: Replay past races and generate strategy recommendations
- Key Features: Event ingestion, deterministic state, strategy engine, fault tolerance, performance metrics
- Team: 2 members (Member A: ingestion/normalization, Member B: replay engine)
- Timeline: 5 checkpoints over semester

**Architecture**: See `docs/architecture.md`  
**Data Sources**: See `docs/data_sources.md`  
**Milestone Plan**: See `docs/milestone_plan.md`  
**User Docs**: See `README.md`