# RaceControl

Deterministic **F1 race replay dashboard** from historical telemetry, with built-in **strategy hints** (undercut/overcut heuristic), live race state, and run metrics. The main product is the one-screen terminal UI in [`scripts/replay_strategy_ui.py`](scripts/replay_strategy_ui.py). A **Hungary 2022 interactive what-if prototype** (`strategy_mvp`) is **in progress** as a separate exploratory track.

## What this repository does

| Piece | Role |
|--------|------|
| **Ingestion** | FastF1 → canonical events (`lap_complete`, `pit_stop`, `track_status`) in [`schemas/event_schema.json`](schemas/event_schema.json). |
| **Replay engine** | [`src/replay/engine.py`](src/replay/engine.py) — walks JSONL in order, updates [`RaceState`](src/replay/state.py) (drivers, gaps, tires, track status). |
| **Strategy engine** | [`src/strategy/engine.py`](src/strategy/engine.py) — on replay, emits periodic + SC/VSC transition recommendations; logs JSONL. |
| **Strategy dashboard (final product)** | [`scripts/replay_strategy_ui.py`](scripts/replay_strategy_ui.py) — one-screen terminal dashboard (dark by default): race table + strategy rows + live metrics strip. |
| **Replay CLI** | [`scripts/replay_cli.py`](scripts/replay_cli.py) — lower-level interactive `play` / `step` / seek / snapshots runner. |
| **What-if (Hungary) — exploratory** | [`src/strategy_mvp/`](src/strategy_mvp/) + [`scripts/strategy_mvp_cli.py`](scripts/strategy_mvp_cli.py) — **work in progress**: prototype to explore counterfactual pits vs a **model benchmark** (simulated; scope and UX still evolving). |

## Quick start

```bash
pip install -r requirements.txt
```

Export a race once (needs FastF1; cache helps offline reuse), then launch the dashboard:

```bash
python scripts/export_events.py --year 2022 --gp Hungary --session R --out data/sample_events_hungary_2022.jsonl
python scripts/replay_strategy_ui.py \
  --events data/sample_events_hungary_2022.jsonl \
  --metrics-json telemetry_report.json
```

At the prompt, use:
- `play` to run continuously
- `speed 1` for real-time, `speed 50` (or higher) for faster-than-real-time
- `pause` / `quit` as needed

For the **Hungary what-if explorer** (separate prototype; full race, no `--max-events`):

```bash
python scripts/export_events.py --year 2022 --gp Hungary --session R --out data/hungary_2022_r.jsonl
```

---

## Data ingestion and events

RaceControl loads sessions via **FastF1**, normalizes fields, sorts events deterministically (time, tie-breakers), assigns `seq`, and can write **JSONL** (one JSON object per line).

**Export CLI**

```bash
python scripts/export_events.py --year 2022 --gp Hungary --session R --out data/your_race.jsonl
```

Common flags: `--year` (2018+), `--gp` (e.g. `Hungary`, `Bahrain`), `--session` (`R`, `Q`, …), `--out`, optional `--max-events` for debugging.

**Programmatic**

```python
# PYTHONPATH must include the repo's `src` directory (as in the project scripts).
from ingest import load_race, build_events

raw = load_race(year=2022, gp="Hungary", session_type="R")
events = build_events(raw)  # sorted list of dicts; see schema for fields
```

**Schema & examples:** [`schemas/event_schema.json`](schemas/event_schema.json), [`schemas/examples/`](schemas/examples/).

---

## Replay: CLI and state

The **race state engine** applies events in file order and never mutates the event list. [`ReplayController`](src/replay/controller.py) adds speed, stepping, and optional callbacks.

### Text replay (`replay_cli.py`)

```bash
python scripts/replay_cli.py --events data/sample_events_hungary_2022.jsonl
```

| Command | Action |
|---------|--------|
| `play` / `pause` | Continuous playback vs hold |
| `step [n]` | Apply `n` events (default 1) |
| `rewind` / `ff` / `jump_time` | Seek by time |
| `speed` | Playback multiplier |
| `status` | Print state |
| `snapshot [seconds]` | Save state under `snapshots/{race_id}/` |
| `quit` | Exit |

Options: `--events` (required), `--race-id`, `--snapshot-interval`, `--initial-speed`.

During **`play`**, status prints are **throttled** per lap (readable terminal); the engine still processes **every** event. At the **last event**, the CLI prints final state and exits.

### Run metrics (latency, throughput, reliability)

Both replay entrypoints can optionally record **run metrics** and write a **post-run report JSON** (latency percentiles, throughput, stream/state issue counts, exceptions, replay drift during `play`).

**Replay CLI**

```bash
python scripts/replay_cli.py \
  --events data/sample_events_hungary_2022.jsonl \
  --metrics-json telemetry_report.json \
  --check-every 500
```

- `--metrics-json`: enables telemetry and writes the report JSON to the given path.
- `--check-every N`: runs state consistency checks every N events (use `0` to only check once at the end).

**Strategy UI**

```bash
python scripts/replay_strategy_ui.py \
  --events data/sample_events_hungary_2022.jsonl \
  --metrics-json telemetry_report.json
```

---

## Strategy recommendations (replay-integrated)

In the dashboard, the right-hand **Strategy engine** panel shows the latest recommendation rows as replay runs.

What you see in the UI:
- One row per driver at each strategy emit point.
- **Call** column: `undercut` / `overcut` / `other` (heuristic lean, not a full race optimizer).
- **Pit** column: `immediate` / `opening` / `hold`.
- **SC** column: `none` / `deployment` / `cleared` / `active`.
- **Tire** column: current compound context for that recommendation.

When rows appear:
- **Periodic emits:** once every 5 laps (configurable with `emit_every_laps`).
- **Track status transitions:** extra emits when SC/VSC is entered or cleared.

Under the hood, this is produced by [`StrategyEngine`](src/strategy/engine.py) on each replay state update (dashboard or CLI).

**Output file (append-only)**

`data/strategy_recs_{race_id}.jsonl`  
(`race_id` defaults from the events filename unless `--race-id` is set.)

Example row shape:

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

---

## Strategy + race dashboard (terminal UI)

Combines **the same replay + strategy logging** with a **Rich** one-screen layout: race/status line, performance strip, driver table, and latest strategy rows.

```bash
python scripts/replay_strategy_ui.py \
  --events data/sample_events_hungary_2022.jsonl \
  --metrics-json telemetry_report.json
```

Uses **`> `** prompt on the **main thread** (works reliably in VS Code / Cursor terminals). Commands: `step [n]`, `play`, `pause`, `speed <x>`, `quit`, `help`. **Empty line** redraws (useful during `play`). Strategy JSONL path is unchanged. Playback does **not** force-process exit on race end so you can read the screen and type `quit`.

Speed notes:
- `speed 1` = real-time replay (same timing as the historical race timeline).
- `speed 20` = 20x faster than real-time.
- `speed 0.5` = half-speed (slower than real-time).

Useful run patterns:
- Fast interactive run: `speed 100`, then `play`.
- Full non-interactive run to completion: use `scripts/replay_cli.py` with `--metrics-json`.
- Light terminal themes: add `--light` to disable the dark dashboard palette.

---

## Hungary 2022 what-if explorer (in progress)

This path is **separate from deterministic replay**: we’re **exploring** a **counterfactual** mode—stint/pit choices against a **simple time model**, rivals fixed to **historical** lap times (they don’t react to you). The CLI, benchmark search, and copy are **prototypes**; expect iteration on physics, UX, and scope.

```bash
python scripts/strategy_mvp_cli.py
# Defaults to data/hungary_2022_r.jsonl — export that file first (see Quick start).
# Or: python scripts/strategy_mvp_cli.py --events path/to/full_race.jsonl
```

Pre-race plans show **model scores** (0–100 rankings in the searched set, not probabilities). The end screen compares your run to a **benchmark** (best among enumerated strategies under the same model). Wording in-tool stays **simulated** / **model**, not real-world optimality.

---

## Tests

```bash
python tests/test_event_schema_examples.py
python tests/test_race_state_engine.py
python -m pytest tests/test_strategy_engine.py tests/test_strategy_mvp.py -v
```

Broader suite (optional):

```bash
python -m pytest tests/ --ignore=tests/run_full_race.py -q
```

---

## Repository map

| Path | Contents |
|------|----------|
| [`src/ingest/`](src/ingest/) | FastF1 loader, `build_events` |
| [`src/replay/`](src/replay/) | `RaceStateEngine`, `ReplayController`, formatting |
| [`src/strategy/`](src/strategy/) | Heuristic strategy engine + JSONL logger |
| [`src/strategy_mvp/`](src/strategy_mvp/) | Hungary what-if prototype (explorer; in progress) |
| [`scripts/`](scripts/) | `export_events`, `replay_cli`, `replay_strategy_ui`, `strategy_mvp_cli`, `hello_world` |
| [`schemas/`](schemas/) | Event JSON Schema + examples |
| [`docs/`](docs/) | Milestones, architecture notes |

More detail for contributors: [`INSTRUCTIONS.md`](INSTRUCTIONS.md), [`docs/milestone_plan.md`](docs/milestone_plan.md).
