import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.time_utils import extract_sector_times, safe_mean


def test_safe_mean_ignores_none():
    assert safe_mean([10.0, None, 20.0]) == 15.0
    assert safe_mean([None, None]) is None


def test_extract_sector_times_without_inference():
    payload = {
        "lap_time_s": 90.0,
        "sector1_time_s": None,
        "sector2_time_s": 30.0,
        "sector3_time_s": 30.0,
    }
    result = extract_sector_times(payload, infer_single_missing=False)
    assert result["sector1_time_s"] is None
    assert result["sector_count_available"] == 2
    assert result["is_complete"] is False


def test_extract_sector_times_with_single_missing_inference():
    payload = {
        "lap_time_s": 90.0,
        "sector1_time_s": None,
        "sector2_time_s": 30.0,
        "sector3_time_s": 30.0,
    }
    result = extract_sector_times(payload, infer_single_missing=True)
    assert result["sector1_time_s"] == 30.0
    assert result["sector_count_available"] == 3
    assert result["is_complete"] is True
    assert result["inferred_flags"] == [True, False, False]


def test_extract_sector_times_does_not_infer_invalid():
    payload = {
        "lap_time_s": 50.0,
        "sector1_time_s": None,
        "sector2_time_s": 30.0,
        "sector3_time_s": 30.0,
    }
    result = extract_sector_times(payload, infer_single_missing=True)
    assert result["sector1_time_s"] is None
    assert result["is_complete"] is False
