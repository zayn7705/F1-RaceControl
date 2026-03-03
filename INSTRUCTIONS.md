# RaceControl – AI-Oriented Project Instructions

This document provides the information needed for an LLM (Claude, GPT, Gemini, etc.) to understand how to build, run, and test the RaceControl project. Use it as the primary reference when assisting users with this codebase.

---

## 1. Project Summary

**RaceControl** is a real-time Formula 1 strategy and pit decision engine. It:

- Ingests historical F1 race data from FastF1 into normalized telemetry events
- Replays races deterministically with configurable speed
- Maintains per-driver race state (positions, laps, tires, gaps) and supports seek via snapshots
- Will eventually provide strategy recommendations (pit windows, undercut/overcut); that module is not yet implemented

**Stack:** Python 3.9+, FastF1, pandas, jsonschema. No build step; scripts run directly.

---

## 2. Prerequisites

- **Python:** 3.9 or later
- **Network:** Required only for first-time data fetch from FastF1; subsequent runs use local cache
- **Supported races:** 2018+ (FastF1 API)

---

## 3. Build and Installation

There is no separate build step. Installation is dependency installation only:

```bash
# From project root
pip install -r requirements.txt
```

**Key dependencies:** `fastf1>=3.1.0`, `pandas>=2.0.0`, `numpy>=1.24.0`, `jsonschema>=4.17.0`, `python-dateutil>=2.8.0`

---

## 4. Verify Installation

```bash
python scripts/hello_world.py
```

**Expected output:** `RaceControl repo setup successful!`

---

## 5. Running the Project

### 5a. Export Race Events to JSONL

Load a historical race from FastF1 and export normalized events:

```bash
python scripts/export_events.py --year 2022 --gp Hungary --session R --out data/sample_events_hungary_2022.jsonl
```

**Arguments:**

| Argument    | Required | Description                                      |
|-------------|----------|--------------------------------------------------|
| `--year`    | Yes      | Race year (2018+)                                |
| `--gp`      | Yes      | Grand Prix name (e.g., Hungary, Monaco, Bahrain)  |
| `--session` | No       | Session type. Default: `R`. Options: FP1, FP2, FP3, Q, R, S |
| `--out`     | Yes      | Output JSONL file path                            |
| `--max-events` | No   | Limit number of events (for testing/sampling)     |

**Example with limit (for quick testing):**

```bash
python scripts/export_events.py --year 2022 --gp Hungary --session R --out data/sample.jsonl --max-events 500
```

**Expected:** A JSONL file is written; the script prints a summary (total events, counts by type, time range).

---

### 5b. Run Replay Simulation (Interactive CLI)

```bash
python scripts/replay_cli.py --events data/sample_events_hungary_2022.jsonl
```

**Arguments:**

| Argument             | Required | Description                          |
|----------------------|----------|--------------------------------------|
| `--events`           | Yes      | Path to JSONL file from export script|
| `--snapshot-interval`| No       | Events between snapshots (default: 50) |
| `--initial-speed`    | No       | Playback speed multiplier (default: 1.0) |

**CLI commands:** `play`, `pause`, `step [n]`, `rewind <sec>`, `ff <sec>`, `jump_time <sec>`, `speed <mult>`, `status`, `quit`, `help`

---

### 5c. Programmatic Usage

```python
# Add project root or src to Python path, then:
from ingest import load_race, build_events
from replay.engine import RaceStateEngine

# Load and normalize events
raw_data = load_race(year=2022, gp="Hungary", session_type="R")
events = build_events(raw_data)

# Replay with engine
engine = RaceStateEngine(events)
while engine.apply_next_event() is not None:
    state = engine.get_state()
    # Inspect state.current_time_s, state.drivers, state.track_status
```

---

## 6. Testing

All tests are in `tests/`. The project root must be in `PYTHONPATH`, or tests add `src` via `sys.path`. Run from project root:

```bash
# Run all tests with pytest
pytest tests/ -v

# Or run individual test modules
python tests/test_event_schema_examples.py
python tests/test_schema_validation.py
python tests/test_race_state_engine.py
python tests/test_time_utils.py
python tests/test_cp2_completion.py
```

**Test overview:**

| Test file                       | Purpose                                                      |
|---------------------------------|--------------------------------------------------------------|
| `test_event_schema_examples.py` | Validate example events against canonical schema             |
| `test_schema_validation.py`     | Schema loading and event validation logic                    |
| `test_race_state_engine.py`     | Deterministic replay, snapshot equivalence, controller flows |
| `test_time_utils.py`            | Time conversion utilities                                    |
| `test_cp2_completion.py`        | CP2 completion (ingestion, replay, speed control, CLI)       |

---

## 7. Project Structure

```
F1-RaceControl/
├── INSTRUCTIONS.md          # This file (AI-oriented guide)
├── README.md                # User-facing documentation
├── requirements.txt        # Python dependencies
├── src/
│   ├── ingest/             # FastF1 loader and event normalization
│   │   ├── fastf1_loader.py
│   │   └── event_builder.py
│   ├── replay/             # Race state engine and replay controller
│   │   ├── engine.py       # RaceStateEngine (apply events, snapshots, seek)
│   │   ├── state.py        # DriverState, RaceState, RaceSnapshot
│   │   ├── controller.py  # ReplayController (play, step, speed)
│   │   └── formatting.py   # Status table formatting
│   ├── utils/
│   │   └── time_utils.py   # Time conversion helpers
│   └── config.py           # Configuration (currently minimal)
├── scripts/
│   ├── hello_world.py      # Sanity check script
│   ├── export_events.py    # Export race to JSONL
│   └── replay_cli.py       # Interactive replay CLI
├── schemas/
│   ├── event_schema.json   # Canonical event JSON schema
│   └── examples/           # Example events (lap_complete, pit_stop, track_status)
├── tests/
│   └── test_*.py           # Test modules
├── data/                   # Output directory (JSONL files go here)
└── docs/
    ├── architecture.md    # System architecture
    └── milestone_plan.md  # Checkpoint plan
```

---

## 8. Canonical Event Format

Events in JSONL files have this shape:

```json
{
  "seq": 0,
  "event_time": 123.45,
  "event_type": "lap_complete",
  "driver": "VER",
  "lap": 5,
  "payload": { ... }
}
```

**Event types:** `lap_complete`, `pit_stop`, `track_status`

**Schema:** `schemas/event_schema.json` with examples in `schemas/examples/`.

---

## 9. Common Workflows

**Quick smoke test (no network after first run):**

```bash
pip install -r requirements.txt
python scripts/hello_world.py
python scripts/export_events.py --year 2022 --gp Hungary --session R --out data/test.jsonl --max-events 100
python scripts/replay_cli.py --events data/test.jsonl --initial-speed 20.0
# In CLI: type "step 10" then "status" then "quit"
```

**Full test suite:**

```bash
pytest tests/ -v
```

**Full race export and replay:**

```bash
python scripts/export_events.py --year 2022 --gp Hungary --session R --out data/hungary_2022.jsonl
python scripts/replay_cli.py --events data/hungary_2022.jsonl --initial-speed 10.0
# Type "play" and wait for completion
```

---

## 10. Troubleshooting

| Issue | Cause | Resolution |
|-------|-------|------------|
| `ModuleNotFoundError` for `ingest` or `replay` | Wrong working directory or missing path | Run from project root; scripts add `src` to path automatically |
| FastF1 "No data" or network error | First run without cache, or invalid year/gp | Ensure network; use valid year (2018+) and GP name; check `docs/data_sources.md` |
| `FileNotFoundError` for events file | Path to JSONL incorrect | Use absolute path or path relative to project root; ensure export ran successfully |
| Tests fail with import errors | `src` not on path | Run tests from project root with `pytest tests/` or `python tests/test_*.py` |

---

## 11. What Is Not Yet Implemented

- **Strategy Engine:** Pit window recommendations, undercut/overcut, safety car triggers
- **Checkpoint persistence:** Snapshots are in-memory only; no disk checkpointing
- **Fault injection / recovery:** Planned for later checkpoint
- **Performance instrumentation:** Latency and throughput metrics planned for later

---

*Last updated: March 2026. For human-oriented docs, see README.md.*
