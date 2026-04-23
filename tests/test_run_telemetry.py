from __future__ import annotations

import sys
from pathlib import Path

# Add src to path (match other tests)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from replay.engine import RaceStateEngine
from replay.instrumented_engine import InstrumentedRaceStateEngine
from replay.run_telemetry import RunTelemetry, summarize_latencies


def test_summarize_latencies_empty() -> None:
    s = summarize_latencies([])
    assert s.count == 0
    assert s.p50_s is None


def test_summarize_latencies_basic_quantiles() -> None:
    s = summarize_latencies([1.0, 2.0, 3.0, 4.0])
    assert s.count == 4
    assert s.min_s == 1.0
    assert s.max_s == 4.0
    assert s.p50_s is not None and 1.0 <= s.p50_s <= 4.0
    assert s.p90_s is not None and s.p90_s >= s.p50_s


def test_instrumented_engine_records_applies_and_seeks() -> None:
    events = [
        {"event_time": 0.0, "seq": 0, "event_type": "track_status", "payload": {"status": "GREEN"}},
        {"event_time": 5.0, "seq": 1, "event_type": "track_status", "payload": {"status": "GREEN"}},
        {"event_time": 10.0, "seq": 2, "event_type": "track_status", "payload": {"status": "GREEN"}},
    ]
    telemetry = RunTelemetry(race_id="test")
    telemetry.start(total_events=len(events))
    engine = InstrumentedRaceStateEngine(RaceStateEngine(events), telemetry)

    assert engine.apply_next_event() is not None
    assert engine.apply_next_event() is not None
    assert telemetry.events_applied == 2
    assert telemetry.apply_next_event_samples.values()

    engine.jump_to_time(0.0)
    assert telemetry.seek_samples.values()

    telemetry.finish(completed=True)
    report = telemetry.report()
    assert report.completed is True
    assert report.events_applied == 2

