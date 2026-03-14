import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from replay.engine import RaceStateEngine  # type: ignore  # noqa: E402
from replay.controller import ReplayController  # type: ignore  # noqa: E402


def _make_synthetic_events():
    # Simple synthetic sequence: two drivers, a pit stop, and a track status
    return [
        {
            "seq": 0,
            "event_time": 10.0,
            "event_type": "lap_complete",
            "driver": "AAA",
            "lap": 1,
            "payload": {
                "lap_time_s": 10.0,
                "compound": "SOFT",
                "stint": 1,
                "tire_age_laps": 1,
                "position": 1,
            },
        },
        {
            "seq": 1,
            "event_time": 11.0,
            "event_type": "lap_complete",
            "driver": "BBB",
            "lap": 1,
            "payload": {
                "lap_time_s": 11.0,
                "compound": "MEDIUM",
                "stint": 1,
                "tire_age_laps": 1,
                "position": 2,
            },
        },
        {
            "seq": 2,
            "event_time": 20.0,
            "event_type": "pit_stop",
            "driver": "AAA",
            "lap": 2,
            "payload": {
                "pit_in_time_s": 20.0,
                "pit_out_time_s": 22.0,
                "pit_duration_s": 2.0,
                "stint": 2,
                "compound_after": "MEDIUM",
            },
        },
        {
            "seq": 3,
            "event_time": 30.0,
            "event_type": "track_status",
            "driver": None,
            "lap": None,
            "payload": {
                "status": "YELLOW",
                "source": "test",
            },
        },
    ]


def test_engine_deterministic_replay_and_state():
    events = _make_synthetic_events()
    engine = RaceStateEngine(events, snapshot_interval_events=1)

    # Apply all events sequentially
    while engine.apply_next_event() is not None:
        pass

    final_state = engine.get_state()
    assert final_state.current_event_index == len(events) - 1
    assert final_state.current_time_s == events[-1]["event_time"]

    # Check driver AAA state
    aaa = final_state.drivers["AAA"]
    assert aaa.lap == 1  # only one lap_complete in synthetic data
    assert aaa.compound == "MEDIUM"  # updated by pit_stop
    assert aaa.stint == 2
    assert aaa.total_pit_stops == 1

    # Check track status
    assert final_state.track_status == "YELLOW"


def test_engine_snapshot_jump_equivalence():
    events = _make_synthetic_events()

    # Baseline: sequential replay to event index 2
    engine_seq = RaceStateEngine(events, snapshot_interval_events=1)
    engine_seq.apply_until_event_index(2)
    seq_state = engine_seq.get_state()

    # Now use jump_to_event directly
    engine_jump = RaceStateEngine(events, snapshot_interval_events=2)
    engine_jump.jump_to_event(2)
    jump_state = engine_jump.get_state()

    # The states should be structurally identical
    assert seq_state.current_event_index == jump_state.current_event_index
    assert seq_state.current_time_s == jump_state.current_time_s
    assert seq_state.track_status == jump_state.track_status
    assert seq_state.drivers.keys() == jump_state.drivers.keys()

    for code in seq_state.drivers.keys():
        d1 = seq_state.drivers[code]
        d2 = jump_state.drivers[code]
        assert d1.__dict__ == d2.__dict__


def _assert_race_state_equal(state1, state2, msg: str = ""):
    """Assert two RaceState instances are identical (for determinism checks)."""
    prefix = f"{msg}: " if msg else ""
    assert state1.current_event_index == state2.current_event_index, (
        f"{prefix}current_event_index {state1.current_event_index} != {state2.current_event_index}"
    )
    assert state1.current_time_s == state2.current_time_s, (
        f"{prefix}current_time_s {state1.current_time_s} != {state2.current_time_s}"
    )
    assert state1.track_status == state2.track_status, (
        f"{prefix}track_status {state1.track_status} != {state2.track_status}"
    )
    assert state1.total_events == state2.total_events, (
        f"{prefix}total_events {state1.total_events} != {state2.total_events}"
    )
    assert state1.drivers.keys() == state2.drivers.keys(), (
        f"{prefix}driver set {set(state1.drivers.keys())} != {set(state2.drivers.keys())}"
    )
    for code in state1.drivers.keys():
        d1, d2 = state1.drivers[code], state2.drivers[code]
        assert d1.__dict__ == d2.__dict__, (
            f"{prefix}driver {code} state differs: {d1.__dict__} vs {d2.__dict__}"
        )


def test_same_final_state_after_two_full_runs():
    """CP3: Running the simulation twice must yield identical final state for all drivers."""
    events = _make_synthetic_events()

    engine1 = RaceStateEngine(events, snapshot_interval_events=2)
    while engine1.apply_next_event() is not None:
        pass
    final1 = engine1.get_state()

    engine2 = RaceStateEngine(events, snapshot_interval_events=2)
    while engine2.apply_next_event() is not None:
        pass
    final2 = engine2.get_state()

    _assert_race_state_equal(final1, final2, "two full runs")
    assert final1.current_event_index == len(events) - 1
    assert "AAA" in final1.drivers and "BBB" in final1.drivers


def test_full_replay_versus_jump_to_end():
    """CP3: Sequential replay to end vs jump_to_event(last) must produce identical state."""
    events = _make_synthetic_events()
    last_index = len(events) - 1

    engine_seq = RaceStateEngine(events, snapshot_interval_events=2)
    while engine_seq.apply_next_event() is not None:
        pass
    seq_final = engine_seq.get_state()

    engine_jump = RaceStateEngine(events, snapshot_interval_events=2)
    engine_jump.jump_to_event(last_index)
    jump_final = engine_jump.get_state()

    _assert_race_state_equal(seq_final, jump_final, "sequential vs jump_to_end")


def test_replay_controller_basic_commands():
    # Use a dummy printer to capture status output
    outputs = []

    def printer(s: str):
        outputs.append(s)

    events = _make_synthetic_events()
    controller = ReplayController(events, snapshot_interval_events=1, initial_speed=10.0, status_printer=printer)

    # Step through a couple of events
    controller.step(2)
    assert controller.engine.get_state().current_event_index == 1

    # Rewind and fast-forward
    controller.rewind(5.0)
    assert controller.engine.get_state().current_time_s <= events[1]["event_time"]

    controller.fast_forward(50.0)
    assert controller.engine.get_state().current_event_index == len(events) - 1

    # Ensure we printed something
    assert outputs

