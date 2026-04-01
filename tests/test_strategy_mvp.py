import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from strategy_mvp.benchmark import compute_benchmark  # noqa: E402
from strategy_mvp.candidates import StrategyPlan, enumerate_candidates  # noqa: E402
from strategy_mvp.index_events import build_race_index, load_events_jsonl  # noqa: E402
from strategy_mvp.physics_simple import (  # noqa: E402
    DEFAULT_PARAMS,
    pit_loss_duration_s,
)
from strategy_mvp.player_state import PlayerState  # noqa: E402
from strategy_mvp.simulator import apply_player_step, run_fixed_plan_total_time  # noqa: E402


FIXTURE = Path(__file__).parent / "fixtures" / "strategy_mvp_minimal.jsonl"


def test_load_fixture_index():
    events = load_events_jsonl(FIXTURE)
    idx = build_race_index(events)
    assert idx.max_lap == 3
    assert "AAA" in idx.drivers and "BBB" in idx.drivers
    assert idx.default_pit_duration_s == 24.0
    assert idx.status_at_time(95.0) == "SC"


def test_pit_loss_sc_less_than_green():
    events = load_events_jsonl(FIXTURE)
    idx = build_race_index(events)
    g = pit_loss_duration_s(idx, "GREEN", DEFAULT_PARAMS)
    s = pit_loss_duration_s(idx, "SC", DEFAULT_PARAMS)
    assert s < g


def test_simulated_position_counterfactual():
    events = load_events_jsonl(FIXTURE)
    idx = build_race_index(events)
    # AAA historically faster — match cumulative at lap 2
    cum_aaa = idx.cumulative_historical_through_lap("AAA", 2)
    order = idx.simulated_positions_at_lap("AAA", 2, cum_aaa)
    assert order[0][0] == "AAA"


def test_player_step_advances():
    events = load_events_jsonl(FIXTURE)
    idx = build_race_index(events)
    st = PlayerState(
        controlled_driver="AAA",
        current_lap=1,
        compound="MEDIUM",
        tire_age_laps=0,
        cumulative_time_s=0.0,
        pit_stops_used=0,
        pit_history=[],
    )
    st2 = apply_player_step(idx, st, None)
    assert st2.current_lap == 2
    assert st2.cumulative_time_s > 0


def test_benchmark_prefers_faster_plan_on_synthetic_grid():
    """Two explicit plans — lower-time plan should rank first."""
    events = []
    seq = 0
    events.append(
        {
            "event_time": 0.0,
            "event_type": "track_status",
            "driver": None,
            "lap": None,
            "payload": {"status": "GREEN", "source": "t"},
            "seq": seq,
        }
    )
    seq += 1
    for lap in range(1, 26):
        for drv, lt in (("AAA", 90.0), ("BBB", 91.0)):
            events.append(
                {
                    "event_time": float(lap * 200 + (1 if drv == "BBB" else 0)),
                    "event_type": "lap_complete",
                    "driver": drv,
                    "lap": lap,
                    "payload": {
                        "lap_time_s": lt,
                        "sector1_time_s": None,
                        "sector2_time_s": None,
                        "sector3_time_s": None,
                        "compound": "MEDIUM",
                        "stint": 1,
                        "tire_age_laps": lap,
                        "tyre_life": None,
                        "position": 1 if drv == "AAA" else 2,
                    },
                    "seq": seq,
                }
            )
            seq += 1

    idx = build_race_index(events)
    assert idx.max_lap >= 25

    slow = StrategyPlan("slow late pit", ["MEDIUM", "HARD"], [22])
    fast = StrategyPlan("fast early pit", ["MEDIUM", "HARD"], [14])
    t_slow = run_fixed_plan_total_time(idx, "AAA", slow)
    t_fast = run_fixed_plan_total_time(idx, "AAA", fast)
    assert t_fast < t_slow

    best, best_t, ranked = compute_benchmark(idx, "AAA")
    assert abs(best_t - min(r[1] for r in ranked)) < 1e-6


def test_enumerate_candidates_bounded():
    plans = enumerate_candidates(70)
    assert len(plans) < 80
    assert any(p.pit_before_laps == [] for p in plans)
