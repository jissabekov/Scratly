"""Plan 05 §5.6 claim math and the seeded deterministic-pipeline measurement."""

from __future__ import annotations

from app.services.checkin_claim_run import measure_seeded_pipeline, response_rate_claim
from app.services.claim_stats import verify_percentile, verify_wilson_ci


def test_wilson_matches_phase1_completion_intervals() -> None:
    after = verify_wilson_ci(19, 21)
    assert round(float(after["point"]), 3) == 0.905
    assert round(float(after["lower"]), 3) == 0.711
    assert round(float(after["upper"]), 3) == 0.973

    before = verify_wilson_ci(7, 21)
    assert round(float(before["point"]), 3) == 0.333
    assert round(float(before["lower"]), 3) == 0.172
    assert round(float(before["upper"]), 3) == 0.546


def test_wilson_matches_phase4_false_fail_interval() -> None:
    interval = verify_wilson_ci(762, 2000)
    assert round(float(interval["point"]), 3) == 0.381
    assert round(float(interval["lower"]), 3) == 0.360
    assert round(float(interval["upper"]), 3) == 0.402


def test_percentile_linear_interpolates() -> None:
    # index = (n - 1) * q; n=4, q=0.5 -> 1.5 between 20 and 30.
    sample = verify_percentile([10, 20, 30, 40], 0.5)
    assert sample["value"] == 25
    upper = verify_percentile([10, 20, 30, 40], 0.95)
    assert abs(float(upper["value"]) - 38.5) < 1e-9
    assert verify_percentile([7, 7, 7], 0.95)["value"] == 7


def test_response_rate_claim_is_blocked_without_deliveries() -> None:
    claim = response_rate_claim(0, 0)
    assert claim["blocked"] is True
    assert claim["target_met"] is False


def test_response_rate_target_is_strictly_above_60_percent() -> None:
    claim = response_rate_claim(60, 100)
    assert claim["blocked"] is False
    assert claim["point"] == 0.6
    assert claim["target_met"] is False
    assert response_rate_claim(61, 100)["target_met"] is True


def test_seeded_pipeline_meets_quiz_and_p95_bars() -> None:
    measured = measure_seeded_pipeline(n=400, warmup=20)
    assert measured["quiz_samples"] > 0
    assert measured["quiz_deliveries"] == 0
    assert measured["quiz_target_met"] is True
    assert float(measured["p95_ms"]) < 100
    assert measured["target_met"] is True
    assert measured["p95"]["method"] == "empirical numpy linear"
