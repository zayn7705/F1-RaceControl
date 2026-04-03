import json
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from replay.engine import RaceStateEngine  # type: ignore  # noqa: E402
from replay.state import DriverState, RaceState  # type: ignore  # noqa: E402
from strategy.engine import StrategyEngine  # type: ignore  # noqa: E402
from strategy.logger import StrategyJsonlLogger  # type: ignore  # noqa: E402


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
    s5.current_event_index = 0
    recs = eng.observe(s5, race_id="x")
    assert recs is not None
    bbb = [r for r in recs if r.driver == "BBB"][0]
    assert bbb.recommendation in {"undercut", "other"}
    assert bbb.pit_window == "immediate"
    assert bbb.safety_car_trigger in {"active", "deployment"}


def test_pit_window_hold_when_tires_fresh():
    eng = StrategyEngine(emit_every_laps=5, max_tire_age_laps=15)
    s5 = _make_state(5, track_status="GREEN")
    s5.drivers["BBB"].compound = "MEDIUM"
    s5.drivers["BBB"].tire_age_laps = 3
    s5.current_event_index = 0
    recs = eng.observe(s5, race_id="x")
    assert recs is not None
    bbb = [r for r in recs if r.driver == "BBB"][0]
    assert bbb.pit_window == "hold"


def test_sc_deployment_emits_even_off_periodic_lap():
    """Track-status transition must emit even when lap % emit_every != 0."""
    eng = StrategyEngine(emit_every_laps=5, max_tire_age_laps=15)
    race_id = "t"

    s3 = _make_state(3, track_status="GREEN")
    s3.current_event_index = 10
    assert eng.observe(s3, race_id=race_id) is None

    s3_sc = _make_state(3, track_status="SC")
    s3_sc.current_event_index = 11
    recs = eng.observe(s3_sc, race_id=race_id)
    assert recs is not None
    assert recs[0].safety_car_trigger == "deployment"
    assert recs[0].pit_window in {"immediate", "opening"}

    # Same event index must not duplicate
    assert eng.observe(s3_sc, race_id=race_id) is None


def test_sc_cleared_emits():
    eng = StrategyEngine(emit_every_laps=5)
    race_id = "t"
    s4_green = _make_state(4, track_status="GREEN")
    s4_green.current_event_index = 19
    assert eng.observe(s4_green, race_id=race_id) is None

    s4_sc = _make_state(4, track_status="SC")
    s4_sc.current_event_index = 20
    assert eng.observe(s4_sc, race_id=race_id) is not None

    s4_clear = _make_state(4, track_status="GREEN")
    s4_clear.current_event_index = 21
    recs = eng.observe(s4_clear, race_id=race_id)
    assert recs is not None
    assert recs[0].safety_car_trigger == "cleared"


def test_empty_drivers_returns_none():
    eng = StrategyEngine()
    st = RaceState(current_event_index=0, current_time_s=1.0, track_status="GREEN", total_events=1)
    st.drivers = {}
    assert eng.observe(st, race_id="x") is None


def test_non_positive_max_lap_returns_none():
    eng = StrategyEngine()
    st = _make_state(0)
    st.drivers["AAA"].lap = 0
    st.drivers["BBB"].lap = 0
    assert eng.observe(st, race_id="x") is None


def test_to_json_dict_shape():
    eng = StrategyEngine(emit_every_laps=5)
    recs = eng.observe(_make_state(5), race_id="race1")
    assert recs is not None
    d = StrategyEngine.to_json_dict(recs[0])
    assert d["race_id"] == "race1"
    assert d["recommendation"] in {"undercut", "overcut", "other"}
    assert "features" in d
    for key in (
        "pit_window",
        "safety_car_trigger",
        "track_status",
        "compound",
        "tire_age_laps",
        "position",
        "gap_to_leader_s",
        "gap_delta_to_leader_s",
        "total_pit_stops",
    ):
        assert key in d["features"]
    json.dumps(d)  # serializable


def test_missing_core_features_returns_other():
    eng = StrategyEngine(emit_every_laps=5)
    s5 = _make_state(5)
    s5.drivers["BBB"].position = None
    recs = eng.observe(s5, race_id="x")
    assert recs is not None
    bbb = [r for r in recs if r.driver == "BBB"][0]
    assert bbb.recommendation == "other"


def test_gap_improving_favors_overcut_when_tires_not_biasing_undercut():
    # SOFT + high tire age dominates scores; use fresh MEDIUM + wide max_tire_age so gap trend wins.
    eng = StrategyEngine(emit_every_laps=5, gap_delta_cutoff_s=0.2, max_tire_age_laps=30)
    race_id = "t"
    eng.observe(_make_state(4), race_id=race_id)
    s5 = _make_state(5)
    s5.drivers["BBB"].compound = "MEDIUM"
    s5.drivers["BBB"].tire_age_laps = 5
    s5.drivers["BBB"].gap_to_leader_s = 1.5  # was 2.0 at lap 4 -> delta -0.5
    recs = eng.observe(s5, race_id=race_id)
    assert recs is not None
    bbb = [r for r in recs if r.driver == "BBB"][0]
    assert bbb.gap_delta_to_leader_s is not None and bbb.gap_delta_to_leader_s < 0
    assert bbb.recommendation in {"overcut", "other"}


def test_periodic_emit_under_ongoing_sc_shows_active():
    eng = StrategyEngine(emit_every_laps=5)
    rid = "x"
    eng.observe(_make_state(4, track_status="GREEN"), race_id=rid)
    s5 = _make_state(5, track_status="SC")
    s5.current_event_index = 1
    eng.observe(s5, race_id=rid)
    s10 = _make_state(10, track_status="SC")
    s10.current_event_index = 2
    recs = eng.observe(s10, race_id=rid)
    assert recs is not None
    assert all(r.safety_car_trigger == "active" for r in recs)


def test_vsc_deployment_emits():
    eng = StrategyEngine(emit_every_laps=5)
    rid = "v"
    s3 = _make_state(3, track_status="GREEN")
    s3.current_event_index = 0
    assert eng.observe(s3, race_id=rid) is None
    s3v = _make_state(3, track_status="VSC")
    s3v.current_event_index = 1
    recs = eng.observe(s3v, race_id=rid)
    assert recs is not None
    assert recs[0].safety_car_trigger == "deployment"


def test_emit_every_lap():
    eng = StrategyEngine(emit_every_laps=1)
    assert eng.observe(_make_state(1), race_id="a") is not None
    assert eng.observe(_make_state(2), race_id="a") is not None


def test_strategy_jsonl_logger_roundtrip():
    eng = StrategyEngine(emit_every_laps=5)
    recs = eng.observe(_make_state(5), race_id="logtest")
    assert recs is not None
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        log = StrategyJsonlLogger(p)
        path = log.append("logtest", recs)
        lines = path.read_text().strip().splitlines()
        assert len(lines) == len(recs)
        row = json.loads(lines[0])
        assert row["features"]["pit_window"] in {"immediate", "opening", "hold"}


def _build_sorted_lap_events(max_lap: int = 6) -> list:
    """Chronological canonical events for two drivers (integration smoke)."""
    events: list = [
        {
            "event_time": 0.0,
            "event_type": "track_status",
            "driver": None,
            "lap": None,
            "payload": {"status": "GREEN", "source": "test"},
        },
    ]
    t = 0.0
    for lap in range(1, max_lap + 1):
        t += 90.0
        events.append(
            {
                "event_time": t,
                "event_type": "lap_complete",
                "driver": "AAA",
                "lap": lap,
                "payload": {
                    "lap_time_s": 90.0,
                    "sector1_time_s": None,
                    "sector2_time_s": None,
                    "sector3_time_s": None,
                    "compound": "MEDIUM",
                    "stint": 1,
                    "tire_age_laps": lap,
                    "tyre_life": None,
                    "position": 1,
                },
            }
        )
        events.append(
            {
                "event_time": t + 0.5,
                "event_type": "lap_complete",
                "driver": "BBB",
                "lap": lap,
                "payload": {
                    "lap_time_s": 91.0,
                    "sector1_time_s": None,
                    "sector2_time_s": None,
                    "sector3_time_s": None,
                    "compound": "MEDIUM",
                    "stint": 1,
                    "tire_age_laps": lap,
                    "tyre_life": None,
                    "position": 2,
                },
            }
        )
    return events


def test_integration_replay_engine_drives_strategy_emissions():
    """End-to-end: RaceStateEngine + StrategyEngine + JSONL logger (same wiring as replay_cli)."""
    events = _build_sorted_lap_events(6)
    engine = RaceStateEngine(events, snapshot_interval_events=1000)
    strat = StrategyEngine(emit_every_laps=5)
    race_id = "integration"
    emissions: list = []
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        logger = StrategyJsonlLogger(base)
        while True:
            st = engine.apply_next_event()
            if st is None:
                break
            recs = strat.observe(st, race_id=race_id)
            if recs:
                emissions.append(recs)
                logger.append(race_id=race_id, recs=recs)
        out = base / f"strategy_recs_{race_id}.jsonl"
        assert out.is_file()
        lines = [ln for ln in out.read_text().splitlines() if ln.strip()]
        assert len(lines) >= 1
        row = json.loads(lines[0])
        assert "recommendation" in row and "features" in row
    # At least one emission at lap 5 periodic tick
    assert len(emissions) >= 1
    any_lap_5 = any(r[0].lap == 5 for r in emissions if r)
    assert any_lap_5

