# RaceControl – Real-Time Formula 1 Strategy & Pit Decision Engine

A real-time systems project for ingesting F1 telemetry events, maintaining deterministic race state, and generating strategy recommendations with fault tolerance and bounded latency.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run hello world to ensure the system runs
python scripts/hello_world.py
```

## Data Ingestion & Event Normalization

RaceControl ingests historical F1 race data from FastF1 and normalizes it into a canonical event format for replay and analysis. The ingestion pipeline loads race sessions, extracts lap timing, pit stops, and track status information, and produces a sorted, timestamped event stream.

### Export Events to JSONL

Export normalized events from a historical F1 race:

```bash
# Export full-race event log for replay
python scripts/export_events.py --year 2022 --gp Hungary --session R --out data/sample_events_hungary_2022.jsonl
```

**Arguments:**
- `--year`: Race year (2018+)
- `--gp`: Grand Prix name (e.g., "Hungary", "Monaco", "Bahrain")
- `--session`: Session type (default: "R" for race). Options: "FP1", "FP2", "FP3", "Q", "R", "S"
- `--out`: Output JSONL file path
- `--max-events`: (Optional) Maximum number of events to export for debugging or sampling

The export script will:
1. Load race data from FastF1 (uses cache if available for offline use)
2. Build normalized events (lap_complete, pit_stop, track_status)
3. Sort events deterministically by time with stable tie-breakers
4. Assign monotonic sequence numbers
5. Export to JSONL format
6. Print summary statistics (total events, counts by type, time range)

### Using the Ingestion API

Programmatically load and normalize race data:

```python
from src.ingest import load_race, build_events

# Load race data from FastF1
raw_data = load_race(year=2022, gp="Hungary", session_type="R")

# Build normalized events
events = build_events(raw_data)

# events is a sorted list of event dictionaries with:
# - seq: monotonic sequence number
# - event_time: seconds since race start
# - event_type: "lap_complete", "pit_stop", or "track_status"
# - driver: driver abbreviation (e.g., "VER") or null
# - lap: lap number or null
# - payload: event-specific data
```

### Event Schema

All events conform to a canonical schema defined in `schemas/event_schema.json`. The schema ensures consistency across the system and supports validation.

**Event Types:**
- `lap_complete`: Lap timing, tire compound, stint, tire age, position
- `pit_stop`: Pit entry/exit times, duration, new compound, stint
- `track_status`: Track status changes (safety car, flags, etc.)

See `schemas/examples/` for example events in the canonical format.

### Features

- **Deterministic Ordering**: Events are sorted by event time, then by type priority, driver, and lap number
- **Monotonic Sequence Numbers**: Sequential integers assigned after sorting for stable event ordering
- **FastF1 Integration**: Uses FastF1 library for accessing historical race data (2018+)
- **Caching Support**: FastF1 cache enabled for offline development and deterministic replay
- **Error Handling**: Clear error messages when race data is unavailable or incomplete
- **Time Normalization**: Converts FastF1 timestamps to race-relative seconds for consistent replay

## Deterministic Race Replay Engine

RaceControl includes a deterministic race replay engine that consumes the canonical JSONL event log and maintains per-driver and global race state over time.

### CLI Replay (`scripts/replay_cli.py`)

Run an interactive replay from a JSONL file:

```bash
python scripts/replay_cli.py --events data/sample_events_hungary_2022.jsonl
```

**Arguments:**
- `--events`: Path to the JSONL file exported by `scripts/export_events.py`
- `--race-id`: Optional identifier used for snapshot output folder (default: derived from the events filename)
- `--snapshot-interval`: Number of events between internal state snapshots (default: 50)
- `--initial-speed`: Initial playback speed multiplier (default: 1.0)

This starts a simple CLI REPL with commands:

- `play`: Start/resume playback, advancing through all events until the end of the race
- `pause`: Pause playback
- `step [n]`: Apply 1 (or `n`) events and print the updated race state
- `rewind <seconds>`: Jump backwards in race time by the given number of seconds
- `ff <seconds>`: Fast-forward in race time by the given number of seconds
- `jump_time <seconds>`: Jump to an absolute race time (seconds since lights out)
- `speed <multiplier>`: Change playback speed (e.g., `2.0` for 2×, `0.5` for half-speed)
- `status`: Print the current race state summary
- `snapshot [seconds]`: Save the current race state to `snapshots/{race_id}/` (optionally jump to `<seconds>` first)
- `quit`: Exit the program

### Strategy Recommendations (Undercut/Overcut Heuristic)

During replay, RaceControl runs a **bounded-time heuristic strategy model** that emits one recommendation per driver **once every 5 laps**. Recommendations are based on the current race-state snapshot fields:

- `track_status`
- `compound`, `tire_age_laps`
- `position`
- `gap_to_leader_s` and per-driver lap-to-lap `gap_delta_to_leader_s`
- `total_pit_stops`

Recommendations are written (append-only) to:

- `data/strategy_recs_{race_id}.jsonl`

Each JSONL row has the form:

```json
{
  "race_id": "hungary_2022",
  "time_s": 3940.038,
  "lap": 35,
  "driver": "VER",
  "recommendation": "overcut",
  "features": {
    "pit_window": "opening",
    "safety_car_trigger": "none",
    "track_status": "GREEN",
    "compound": "MEDIUM",
    "tire_age_laps": 8,
    "position": 2,
    "gap_to_leader_s": 5.123,
    "gap_delta_to_leader_s": -0.350,
    "total_pit_stops": 1
  }
}
```

`pit_window` is `immediate` (pit this stint soon), `opening` (window in the next few laps), or `hold` (extend). `safety_car_trigger` is `none`, `deployment` (SC/VSC just started), `cleared` (back to green/yellow racing), or `active` (caution period ongoing on a periodic tick).

### Strategy + race dashboard (terminal UI)

For a single screen that shows **live race state** (running order, gaps, tires) and the **latest strategy rows** together, use the Rich-based UI (requires `rich` in [`requirements.txt`](requirements.txt)):

```bash
python scripts/replay_strategy_ui.py --events data/sample_events_hungary_2022.jsonl
```

Commands: `step [n]`, `play`, `pause`, `speed <multiplier>`, `quit`, `help`. The same JSONL log is still written to `data/strategy_recs_{race_id}.jsonl`. The UI redraws after each command (and on an **empty line** / Enter to refresh while the race is playing). Playback no longer force-exits the process when the race ends so you can read the dashboard and type `quit`.

During continuous playback (`play`):

- The engine applies **every event in the log** in canonical order and runs until the final event is reached.
- The CLI prints a tabular view of **all drivers** (up to 20), including:
  - Position, driver code, lap
  - Gap to leader on the current lap (derived from lap completion times)
  - Tire compound, stint number, tire age in laps
  - Last lap time in seconds
- Output is throttled to a small, fixed number of prints per lap to keep the terminal readable, but no events are skipped in the engine.
- When the last event has been applied, the CLI prints the final race state, shows a `Race complete. Exiting.` message, and terminates.

Internally, the replay engine (`src/replay/engine.py`) maintains a `RaceState` with:

- Per-driver state (`DriverState`): lap, position, compound, stint, tire age, last lap time, gap to leader, pit-stop count
- Global state: current event index, race-relative time, track status
- In-memory snapshots for efficient, deterministic rewind/fast-forward and time jumps
- User-triggered disk snapshots via the `snapshot` CLI command (saved under `snapshots/{race_id}/`)

Given the same JSONL event log, the replay engine guarantees deterministic state evolution and identical CLI output for the same sequence of user commands.

### Interactive what-if strategy MVP (Hungary 2022)

Counterfactual lap-by-lap mode: pick a driver, see **model-ranked** dry strategies (scores 0–100 are relative rankings, not probabilities), drive the race with optional pits, then compare your **simulated** total time to a **benchmark** chosen as the fastest among a finite set of candidate strategies under the same simple model. Rivals keep historical lap times; they do not react to your strategy.

**Export full race events** (required once; needs FastF1 cache/network as for other exports):

```bash
python scripts/export_events.py --year 2022 --gp Hungary --session R --out data/hungary_2022_r.jsonl
```

**Run the interactive CLI** (defaults to `data/hungary_2022_r.jsonl`):

```bash
python scripts/strategy_mvp_cli.py
# Or: python scripts/strategy_mvp_cli.py --events path/to/your.jsonl
```

Outputs are explicitly labeled *simulated* in the tool. The benchmark is **not** a claim of real-world optimality.

### Running Tests

```bash
# Test schema validation and example events
python tests/test_event_schema_examples.py
python tests/test_race_state_engine.py
python -m pytest tests/test_strategy_engine.py tests/test_strategy_mvp.py -v
```

The test suite validates that example events conform to the canonical schema, includes a smoke test for the event building pipeline, and tests the deterministic race state engine (event application, snapshots, and basic CLI controller flows).
