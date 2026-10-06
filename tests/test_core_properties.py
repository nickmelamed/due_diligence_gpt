"""Characterization and property tests for the numeric core.

These pin what the code does today. Where today's behavior looks wrong, the
test says so and names the follow-up in PROGRESS.md.
"""
import math

import pytest
from hypothesis import given, strategies as st

from ddgpt.config import ToleranceConfig
from ddgpt.extract.postprocess import temporal_weight
from ddgpt.pipeline.scoring import compute_agreement, final_confidence
from ddgpt.risk.engine import RiskEngine
from ddgpt.rules.numeric_mismatch import NumericMismatchRule, pct_delta
from ddgpt.utils.cache import content_hash, disk_cached

finite = st.floats(min_value=-1e12, max_value=1e12, allow_nan=False, allow_infinity=False)
unit_interval = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)


# compute_agreement

def test_agreement_is_one_with_fewer_than_two_values():
    assert compute_agreement([]) == 1.0
    assert compute_agreement([5.0]) == 1.0
    assert compute_agreement([None, 5.0, None]) == 1.0


def test_agreement_is_one_inside_tolerance():
    assert compute_agreement([100.0, 104.0]) == 1.0


def test_agreement_degrades_linearly_past_tolerance():
    # spread 20 over mean magnitude 110 is about 0.1818
    assert compute_agreement([100.0, 120.0]) == pytest.approx(1.0 - 20.0 / 110.0)


def test_agreement_of_two_zeros_is_one():
    assert compute_agreement([0.0, 0.0]) == 1.0


@given(st.lists(st.one_of(finite, st.none()), max_size=6))
def test_agreement_stays_in_unit_interval(values):
    assert 0.0 <= compute_agreement(values) <= 1.0


@given(finite, finite)
def test_agreement_is_symmetric(a, b):
    assert compute_agreement([a, b]) == compute_agreement([b, a])


# pct_delta

def test_pct_delta_worked_example():
    assert pct_delta(100.0, 110.0) == pytest.approx(10.0 / 105.0)


def test_pct_delta_of_zeros_is_zero():
    assert pct_delta(0.0, 0.0) == 0.0


@given(finite, finite)
def test_pct_delta_is_symmetric_and_bounded(a, b):
    assert pct_delta(a, b) == pct_delta(b, a)
    assert 0.0 <= pct_delta(a, b) <= 2.0


@given(finite)
def test_pct_delta_of_equal_values_is_zero(a):
    assert pct_delta(a, a) == 0.0


# final_confidence

def test_final_confidence_weights_sum_to_one():
    assert final_confidence(1.0, 1.0, 1.0, 1.0) == pytest.approx(1.0)
    assert final_confidence(0.0, 0.0, 0.0, 0.0) == 0.0


def test_final_confidence_worked_example():
    assert final_confidence(0.8, 0.9, 0.5, 0.5) == pytest.approx(0.35 * 0.8 + 0.25 * 0.9 + 0.2 * 0.5 + 0.2 * 0.5)


@given(unit_interval, unit_interval, unit_interval, unit_interval)
def test_final_confidence_is_monotonic_in_each_input(base, a, b, c):
    low = final_confidence(base, a, b, c)
    assert final_confidence(min(1.0, base + 0.1), a, b, c) >= low
    assert final_confidence(base, min(1.0, a + 0.1), b, c) >= low
    assert final_confidence(base, a, min(1.0, b + 0.1), c) >= low
    assert final_confidence(base, a, b, min(1.0, c + 0.1)) >= low
    assert 0.0 <= low <= 1.0 + 1e-9


# risk score

@given(st.lists(st.sampled_from(["RED", "YELLOW"]), max_size=40))
def test_risk_score_is_in_unit_interval(severities):
    assert 0.0 <= RiskEngine.score_from_severities(severities) < 1.0


@given(st.lists(st.sampled_from(["RED", "YELLOW"]), max_size=20))
def test_adding_a_flag_never_lowers_the_score(severities):
    before = RiskEngine.score_from_severities(severities)
    assert RiskEngine.score_from_severities(severities + ["YELLOW"]) >= before


def test_risk_score_worked_value_for_one_red():
    assert RiskEngine.score_from_severities(["RED"]) == pytest.approx(1.0 - math.exp(-0.5))


def test_unknown_severity_counts_as_point_three():
    assert RiskEngine.score_from_severities(["ORANGE"]) == pytest.approx(1.0 - math.exp(-0.3 / 2.0))


# temporal_weight

def test_temporal_weight_is_neutral_without_a_date():
    assert temporal_weight(None) == 0.5
    assert temporal_weight("") == 0.5


def test_temporal_weight_for_a_timezone_aware_date_decays_with_age():
    recent = temporal_weight("2026-01-01T00:00:00+00:00")
    old = temporal_weight("2016-01-01T00:00:00+00:00")
    assert 0.3 <= old <= recent <= 1.0


def test_temporal_weight_is_neutral_for_unparseable_text():
    assert temporal_weight("not a date") == 0.5


def test_temporal_weight_ignores_plain_dates_known_bug():
    # Known bug, to be fixed after the standards work (see PROGRESS.md).
    # A date without a timezone is subtracted from an aware "now", the
    # TypeError is swallowed, and every plain date gets the neutral 0.5.
    # When this is fixed, a recent plain date should score well above 0.5
    # and a future one should clamp to 1.0, so flip these assertions.
    assert temporal_weight("2024-01-01") == 0.5
    assert temporal_weight("2020-01-01") == 0.5
    assert temporal_weight("2999-01-01") == 0.5


# tolerance selection in NumericMismatchRule

def _tol(name, unit):
    return NumericMismatchRule(ToleranceConfig())._tolerance_for(name, unit)


def test_tolerance_defaults_by_unit():
    assert _tol("custom_usd", "usd") == ("relative", 0.03)
    assert _tol("custom_pct", "percent") == ("absolute", 2.0)
    assert _tol("custom_x", "multiple") == ("relative", 0.05)
    assert _tol("custom_n", "count") == ("absolute", 1.0)
    assert _tol("custom_y", "year") == ("absolute", 0.0)
    assert _tol("custom_other", "other") == ("absolute", 2.0)


def test_management_fee_keeps_its_tighter_absolute_tolerance():
    assert _tol("mgmt_fee", "percent") == ("absolute", 0.25)


def test_aum_mismatch_is_red_and_unknown_metrics_are_yellow():
    rule = NumericMismatchRule(ToleranceConfig())
    assert rule._severity_for("aum") == "RED"
    assert rule._severity_for("some_custom_metric") == "YELLOW"


# cache keys

def test_content_hash_is_stable_and_24_hex_chars():
    key = content_hash("a", "b", b"c")
    assert key == content_hash("a", "b", b"c")
    assert len(key) == 24
    int(key, 16)


@given(st.text(), st.text())
def test_content_hash_changes_with_input(a, b):
    if a != b:
        assert content_hash(a) != content_hash(b)


def test_disk_cached_computes_once_then_reads_back(tmp_path):
    calls = []

    def compute():
        calls.append(1)
        return {"x": 1}

    assert disk_cached(str(tmp_path), "ns", "k", compute) == {"x": 1}
    assert disk_cached(str(tmp_path), "ns", "k", compute) == {"x": 1}
    assert len(calls) == 1


def test_disk_cached_recomputes_when_the_entry_is_corrupt(tmp_path):
    path = tmp_path / "ns" / "k.pkl"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"not a pickle")
    assert disk_cached(str(tmp_path), "ns", "k", lambda: 7) == 7


def test_disk_cached_skips_the_cache_when_disabled(tmp_path):
    assert disk_cached(str(tmp_path), "ns", "k", lambda: 1, enabled=False) == 1
    assert not (tmp_path / "ns").exists()
