# RaceControl Demo Run Guide (Start to Finish)

This guide takes you from a fresh clone to running the full terminal dashboard demo.

## 1) Clone the repository

```bash
git clone https://github.com/<your-org-or-user>/F1-RaceControl.git
cd F1-RaceControl
```

## 2) Create and activate a Python environment

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Windows (PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

## 3) Install dependencies

```bash
pip install -r requirements.txt
```

## 4) Export race events (one-time setup for demo data, we'll explore the Hungary 2022 GP)

```bash
python scripts/export_events.py --year 2022 --gp Hungary --session R --out data/sample_events_hungary_2022.jsonl
```

If the file already exists, you can reuse it.

## 5) Start the dashboard demo

```bash
python scripts/replay_strategy_ui.py \
  --events data/sample_events_hungary_2022.jsonl \
  --metrics-json telemetry_report.json
```

You should see the one-screen dashboard with:
- race state panel (left)
- strategy panel (right)
- performance strip at the top

## 6) Run the simulation interactively

At the `>` prompt:

1. Type:

```text
play
```

2. Press **Enter**.

### Important: refresh behavior

After typing `play`, you must press **Enter** again (empty line) to refresh/redraw the screen and see updated output while it is running.

- `Enter` on an empty prompt = refresh screen
- `pause` = pause simulation
- `speed 1` = real-time
- `speed 50` = 50x faster
- `quit` = exit

## 7) Suggested demo flow (quick script)

At the prompt, run:

```text
speed 50
play
```

Then press **Enter** every few seconds to refresh and show progress.

To pause and explain:

```text
pause
```

To continue:

```text
play
```

Then press **Enter** to refresh.

To finish:

```text
quit
```

## 8) Demo outputs

During/after the run:
- Strategy recommendations are logged to:
  - `data/strategy_recs_hungary_2022.jsonl`
- Run metrics are written to:
  - `telemetry_report.json`

## Troubleshooting

- If dashboard does not render correctly:
  - enlarge terminal window
  - try `--light` for light terminal themes:

```bash
python scripts/replay_strategy_ui.py \
  --events data/sample_events_hungary_2022.jsonl \
  --metrics-json telemetry_report.json \
  --light
```

- If dependencies fail:
  - confirm Python 3.10+ and rerun `pip install -r requirements.txt`
- If data export fails:
  - check internet access for FastF1 data fetch and retry
