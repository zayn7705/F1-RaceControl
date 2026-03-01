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
python scripts/export_events.py --year 2022 --gp Hungary --session R --out data/sample_events_hungary_2022.jsonl --max-events 500
```

**Arguments:**
- `--year`: Race year (2018+)
- `--gp`: Grand Prix name (e.g., "Hungary", "Monaco", "Bahrain")
- `--session`: Session type (default: "R" for race). Options: "FP1", "FP2", "FP3", "Q", "R", "S"
- `--out`: Output JSONL file path
- `--max-events`: (Optional) Maximum number of events to export

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

### Running Tests

```bash
# Test schema validation and example events
python tests/test_event_schema_examples.py
```

The test suite validates that example events conform to the canonical schema and includes a smoke test for the event building pipeline.
