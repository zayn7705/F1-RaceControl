# RaceControl

Deterministic **F1 race replay** from historical telemetry, plus **strategy hints** (undercut/overcut heuristic). A **Hungary 2022 interactive what-if prototype** (`strategy_mvp`) is **in progress**—a space to explore counterfactual pit/stint play and model benchmarks, not a finished product. Built as a real-time systems course project: same event log → same state; bounded, explainable strategy logic.

## What this repository does

| Piece | Role |
|--------|------|
| **Ingestion** | FastF1 → canonical events (`lap_complete`, `pit_stop`, `track_status`) in [`schemas/event_schema.json`](schemas/event_schema.json). |
| **Replay engine** | [`src/replay/engine.py`](src/replay/engine.py) — walks JSONL in order, updates [`RaceState`](src/replay/state.py) (drivers, gaps, tires, track status). |
| **Strategy engine** | [`src/strategy/engine.py`](src/strategy/engine.py) — on replay, emits periodic + SC/VSC transition recommendations; logs JSONL. |
| **Replay CLI** | [`scripts/replay_cli.py`](scripts/replay_cli.py) — interactive `play` / `step` / seek / snapshots. |
| **Strategy dashboard** | [`scripts/replay_strategy_ui.py`](scripts/replay_strategy_ui.py) — one terminal view: race table + latest strategy rows (needs `rich`). |
| **What-if (Hungary) — exploratory** | [`src/strategy_mvp/`](src/strategy_mvp/) + [`scripts/strategy_mvp_cli.py`](scripts/strategy_mvp_cli.py) — **work in progress**: prototype to explore counterfactual pits vs a **model benchmark** (simulated; scope and UX still evolving). |

## Quick start

```bash
pip install -r requirements.txt
python scripts/hello_world.py
```

Export a race once (needs FastF1; cache helps offline reuse):

```bash
python scripts/export_events.py --year 2022 --gp Hungary --session R --out data/sample_events_hungary_2022.jsonl
```

For the **Hungary what-if explorer** (full race, no `--max-events`):

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

---

## Strategy recommendations (replay-integrated)

While events are applied (replay CLI or strategy UI), [`StrategyEngine`](src/strategy/engine.py) runs on each state update and can emit **one row per driver** when:

- **Periodic:** `max(lap)` is a multiple of **5** (configurable `emit_every_laps`), once per lap tick; or  
- **SC/VSC transitions:** track status **enters** or **leaves** safety car / VSC (extra emit so triggers are not missed between 5-lap ticks).

**Labels**

- **`recommendation`:** `undercut` / `overcut` / `other` — rough lean toward **stopping earlier** vs **staying out** from a **heuristic** (tires, gaps, position, SC), not a full race simulation.
- **`pit_window`:** `immediate` / `opening` / `hold` — simple stint window hint.
- **`safety_car_trigger`:** `none` / `deployment` / `cleared` / `active` — caution-related signal on that row.

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

Combines **the same replay + strategy logging** with a **Rich** layout: header (time, event index, track), driver table, latest strategy rows.

```bash
python scripts/replay_strategy_ui.py --events data/sample_events_hungary_2022.jsonl
```

Uses **`> `** prompt on the **main thread** (works reliably in VS Code / Cursor terminals). Commands: `step [n]`, `play`, `pause`, `speed`, `quit`, `help`. **Empty line** redraws (useful during `play`). Strategy JSONL path is unchanged. Playback does **not** force-process exit on race end so you can read the screen and type `quit`.

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
