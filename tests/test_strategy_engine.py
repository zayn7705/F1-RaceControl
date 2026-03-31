import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from replay.state import DriverState, RaceState  # type: ignore  # noqa: E402
from strategy.engine import StrategyEngine  # type: ignore  # noqa: E402


def _make_state(lap: int, *, track_status: str | None = "GREEN") -> RaceState:
    state = RaceState(current_event_index=0, current_time_s=100.0, track_status=track_status, total_events=999)
    state.drivers = {
        "AAA": DriverState(
            driver_code="AAA",
            lap=lap,
            position=1,
            compound="MEDIUM",
            stint=1,
            tire_age_laps=5,
            gap_to_leader_s=0.0,
            total_pit_stops=1,
        ),
        "BBB": DriverState(
            driver_code="BBB",
            lap=lap,
            position=2,
            compound="SOFT",
            stint=1,
            tire_age_laps=12,
            gap_to_leader_s=2.0,
            total_pit_stops=1,
        ),
    }
    return state


def test_emits_only_every_5_laps():
    eng = StrategyEngine(emit_every_laps=5)
    race_id = "test_race"

    assert eng.observe(_make_state(4), race_id=race_id) is None
    recs = eng.observe(_make_state(5), race_id=race_id)
    assert recs is not None
    assert len(recs) == 2

    # Same lap should not emit twice
    assert eng.observe(_make_state(5), race_id=race_id) is None

    assert eng.observe(_make_state(6), race_id=race_id) is None
    assert eng.observe(_make_state(10), race_id=race_id) is not None


def test_deterministic_driver_ordering():
    eng = StrategyEngine(emit_every_laps=5)
    recs = eng.observe(_make_state(5), race_id="x")
    assert recs is not None
    # Sorted by position then driver_code => AAA (pos 1) then BBB (pos 2)
    assert [r.driver for r in recs] == ["AAA", "BBB"]


def test_gap_delta_sign_affects_recommendation_direction():
    eng = StrategyEngine(emit_every_laps=5, gap_delta_cutoff_s=0.2, max_tire_age_laps=15)
    race_id = "test_race"

    # Prime memory at lap 4 (BBB gap = 2.0)
    s4 = _make_state(4)
    assert eng.observe(s4, race_id=race_id) is None

    # At lap 5 BBB gap increases -> should lean undercut (especially with SOFT + older tires)
    s5 = _make_state(5)
    s5.drivers["BBB"].gap_to_leader_s = 2.5  # +0.5 delta
    recs = eng.observe(s5, race_id=race_id)
    assert recs is not None
    bbb = [r for r in recs if r.driver == "BBB"][0]
    assert bbb.gap_delta_to_leader_s is not None and bbb.gap_delta_to_leader_s > 0
    assert bbb.recommendation in {"undercut", "other"}


def test_sc_bias_can_favor_undercut():
    eng = StrategyEngine(emit_every_laps=5, max_tire_age_laps=10)
    s5 = _make_state(5, track_status="SC")
    s5.drivers["BBB"].tire_age_laps = 15
    recs = eng.observe(s5, race_id="x")
    assert recs is not None
    bbb = [r for r in recs if r.driver == "BBB"][0]
    assert bbb.recommendation in {"undercut", "other"}

