# AI Workflow Instructions

**Purpose**: This document enables AI agents (LLMs) to quickly understand, build, run, and test the RaceControl project when starting a new conversation.

## Quick Context for AI Agents

**Project**: RaceControl - Real-Time Formula 1 Strategy & Pit Decision Engine  
**Current Status**: Checkpoint 2 (CP2) complete - Ingestion + Replay Engine working  
**Language**: Python 3.8+  
**Main Goal**: Replay historical F1 races as real-time event streams with configurable speed control

**What Works Now**:
- ✅ Load historical F1 race data from FastF1 (2018+)
- ✅ Normalize events into canonical JSONL format
- ✅ Replay races with speed control (1x, 5x, 20x)
- ✅ Maintain deterministic race state (positions, gaps, tires, lap times)

**What's Next** (Future checkpoints):
- Strategy decision engine (CP4)
- Performance metrics (CP5)
- Fault tolerance (CP5)

---

## Project Structure (Quick Reference)

```
src/
├── ingest/              # Data ingestion (FASTF1 → normalized events)
│   ├── fastf1_loader.py    # load_race(year, gp, session_type)
│   └── event_builder.py    # build_events(raw_data) → List[events]
├── replay/              # Replay engine (events → race state)
│   ├── engine.py          # RaceStateEngine - applies events deterministically
│   ├── controller.py      # ReplayController - speed control, play/pause
│   └── state.py           # RaceState, DriverState - data structures
└── utils/
    └── time_utils.py      # None-safe sector time utilities

scripts/
├── export_events.py    # CLI: Export race to JSONL
└── replay_cli.py       # CLI: Interactive replay

schemas/
├── event_schema.json   # Canonical event format (JSON Schema)
└── examples/           # Example events for each type

tests/                  # Test suite (pytest)
```

---

## Setup (One-Time)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Verify (should print "RaceControl repo setup successful!")
python scripts/hello_world.py
```

**Key Dependencies**: `fastf1`, `pandas`, `jsonschema`, `pytest`

---

## Core Workflows for AI Agents

### Workflow 1: Export and Replay a Race

```bash
# Step 1: Export events
python scripts/export_events.py \
    --year 2022 --gp Hungary --session R \
    --out data/hungary_2022.jsonl

# Step 2: Replay
python scripts/replay_cli.py \
    --events data/hungary_2022.jsonl \
    --initial-speed 5.0
```

**In REPL**: `play`, `pause`, `speed 20`, `status`, `quit`

### Workflow 2: Programmatic Usage

```python
from src.ingest import load_race, build_events
from src.replay import RaceStateEngine

# Load and normalize
raw = load_race(2022, "Hungary", "R")
events = build_events(raw)  # Returns List[dict] with normalized events

# Process events
engine = RaceStateEngine(events)
state = engine.apply_next_event()  # Returns RaceState
```

---

## Event Schema (Critical for AI Agents)

**Location**: `schemas/event_schema.json`

**Event Structure**:
```python
{
    "seq": int,                    # Monotonic sequence (0, 1, 2, ...)
    "event_time": float,           # Seconds since race start
    "event_type": str,             # "lap_complete" | "pit_stop" | "track_status"
    "driver": str | None,          # Driver code (e.g., "VER") or null
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
   - `status` (e.g., "GREEN", "YELLOW", "VSC", "SC")
   - `source` ("fastf1_track_status")

**Validation**: Use `jsonschema.validate(instance=event, schema=schema)`

---

## Key APIs for AI Agents

### `load_race(year: int, gp: str, session_type: str = "R") -> dict`

Loads race data from FastF1. Creates cache automatically.

**Returns**: `{"session": FastF1Session, "laps": DataFrame, "timing_data": ...}`  
**Raises**: `ValueError` if race not found or year < 2018

### `build_events(raw_data: dict) -> List[dict]`

Normalizes FastF1 data to canonical events.

**Returns**: Sorted list of event dicts (by time, then type priority, driver, lap)  
**Side Effect**: Assigns monotonic `seq` numbers (0, 1, 2, ...)

### `RaceStateEngine(events: List[dict], snapshot_interval_events: int = 50)`

Deterministic state engine. **Key methods**:
- `apply_next_event() -> RaceState | None` - Apply next event
- `get_state() -> RaceState` - Get current state (read-only copy)
- `jump_to_time(time_s: float) -> RaceState` - Seek to absolute time

### `ReplayController(events: List[dict], initial_speed: float = 1.0)`

Replay with speed control. **Key methods**:
- `play()` - Start/resume (runs in background thread)
- `pause()` - Pause playback
- `set_speed(speed: float)` - Change speed multiplier
- `step(n: int = 1)` - Step through n events

---

## Testing Commands

```bash
# Schema validation
python tests/test_event_schema_examples.py

# State engine
python tests/test_race_state_engine.py

# Time utilities
python -m pytest tests/test_time_utils.py -v

# CP2 completion check
python tests/test_cp2_completion.py
```

**Expected**: All tests pass. Smoke test may skip if cache not warm (acceptable).

---

## Important Implementation Details for AI Agents

### Determinism
- **Same events → same state**: RaceStateEngine is fully deterministic
- **Event ordering**: Sorted by `(event_time, type_priority, driver, lap)`
- **Sequence numbers**: Assigned after sorting (0, 1, 2, ...)

### Missing Data Handling
- **Sector times**: May be `None` on lap 1 (expected). Use `src.utils.time_utils.extract_sector_times()` for safe handling
- **Pit durations**: Now properly extracted (was fixed in recent commit)
- **Track status**: Extracted from `session.track_status` DataFrame

### State Immutability
- `RaceStateEngine.get_state()` returns **deep copy** - safe to modify
- Engine internal state is never mutated by external code

### Thread Safety
- `ReplayController` uses locks for thread-safe playback
- Background thread handles timing; main thread handles commands

### Caching
- FastF1 cache in `cache/` directory (auto-created)
- First run downloads data; subsequent runs use cache (offline-capable)

---

## Common Tasks for AI Agents

### Task: Add a New Feature

1. **Understand the schema**: Read `schemas/event_schema.json`
2. **Check existing patterns**: Look at `src/ingest/event_builder.py` for extraction patterns
3. **Update schema if needed**: Add fields to `event_schema.json`
4. **Update builder**: Modify `_build_*_events()` functions
5. **Update state engine**: Modify `_apply_*()` in `src/replay/engine.py` if needed
6. **Add tests**: Create test in `tests/`
7. **Validate**: Run `python tests/test_event_schema_examples.py`

### Task: Debug Event Processing

```python
from src.ingest import load_race, build_events

raw = load_race(2022, "Hungary", "R")
events = build_events(raw)

# Inspect events
print(f"Total: {len(events)}")
print(f"Types: {Counter(e['event_type'] for e in events)}")

# Check specific event
event = events[100]
print(f"Event 100: {event['event_type']} at {event['event_time']:.1f}s")
print(f"Payload: {event['payload']}")
```

### Task: Validate Event Schema

```python
import json
import jsonschema

schema = json.load(open('schemas/event_schema.json'))
event = json.load(open('schemas/examples/lap_complete.json'))

jsonschema.validate(instance=event, schema=schema)  # Raises if invalid
```

---

## Troubleshooting for AI Agents

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: fastf1` | Run `pip install -r requirements.txt` |
| `Cache directory does not exist` | Auto-created, but can `mkdir -p cache` |
| `Failed to load race data` | Check year >= 2018, verify GP name spelling, ensure internet for first download |
| `No events loaded` | Verify export script ran successfully, check JSONL file exists |
| Tests skip with "cache not warm" | Run export script once to warm cache |

---

## File Quick Reference

| What You Need | File Location |
|---------------|---------------|
| Load FastF1 data | `src/ingest/fastf1_loader.py` → `load_race()` |
| Build events | `src/ingest/event_builder.py` → `build_events()` |
| Replay engine | `src/replay/engine.py` → `RaceStateEngine` |
| Speed control | `src/replay/controller.py` → `ReplayController` |
| Event schema | `schemas/event_schema.json` |
| Export CLI | `scripts/export_events.py` |
| Replay CLI | `scripts/replay_cli.py` |
| Time utilities | `src/utils/time_utils.py` |

---

## Success Criteria (CP2)

CP2 is complete when:
- ✅ Can export events from historical race (2018+)
- ✅ Can replay with configurable speed (1x, 5x, 20x tested)
- ✅ Events deterministically sorted and sequenced
- ✅ State engine maintains correct driver state
- ✅ All tests pass

**Verification**: Run `python tests/test_cp2_completion.py`

---

## How to Help the User (For AI Agents)

When the user asks for help:

1. **Check current state**: Run tests to see what's working
2. **Understand the schema**: Always validate against `schemas/event_schema.json`
3. **Maintain determinism**: Never introduce randomness or non-deterministic behavior
4. **Handle missing data**: Use `src.utils.time_utils` for None-safe operations
5. **Test changes**: Run test suite after modifications
6. **Follow patterns**: Look at existing code in `src/ingest/` and `src/replay/` for patterns

**Common User Requests**:
- "Add new event type" → Update schema, builder, state engine, tests
- "Fix data extraction" → Check `event_builder.py`, verify FastF1 data availability
- "Improve replay" → Modify `controller.py` or `engine.py`
- "Add feature" → Follow existing patterns, maintain determinism, add tests

---

## Quick Start for New AI Sessions

**If user says "help me with RaceControl"**:

1. Read this file to understand project structure
2. Check `schemas/event_schema.json` for event format
3. Run `python tests/test_event_schema_examples.py` to verify setup
4. Ask user what they want to do (add feature, fix bug, etc.)

**If user says "implement X"**:

1. Understand X in context of existing codebase
2. Check if schema needs updates
3. Follow patterns in `src/ingest/` or `src/replay/`
4. Maintain determinism and test coverage
5. Update tests if needed

---

## Notes

- **Python version**: 3.8+ (tested with 3.13)
- **Cache location**: `cache/` (gitignored, auto-created)
- **Data location**: `data/*.jsonl` (gitignored)
- **Determinism is critical**: Same events must produce same state
- **Schema is authoritative**: Always validate against `schemas/event_schema.json`
