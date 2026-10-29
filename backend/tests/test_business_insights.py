"""
Phase 9 Business Insights, Recommendations, and Monitoring Test Suite
ForecastIQ Backend

Covers:
- Missing price values vs genuine zero prices
- No holiday records vs genuine recorded holiday events
- Forecast peak and trough dates within 7D, 28D, and 90D horizons
- CA_2 / CA_3 store switching
- Correct scope in insight response
- Unavailable data states
- Stale-result cache prevention
"""
import pytest
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.data.schema import (
    ForecastResult,
    InsightRequest,
    BusinessInsightsResponse,
    MonitoringReport,
)
from app.data.loader import save_dataset
from app.insights.business_insights import BusinessInsightEngine, BusinessThresholds, INSIGHTS_CACHE
from app.insights.monitoring import MonitoringTracker

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_hist_df(n_days=60, baseline=100.0, series_id="TEST_SERIES_INSIGHT",
                 price_col=None, holiday_col=None):
    dates = pd.date_range("2024-01-01", periods=n_days, freq="D")
    df = pd.DataFrame({
        "date": dates,
        "series_id": series_id,
        "target": [baseline] * n_days,
    })
    if price_col is not None:
        df["price"] = price_col
    if holiday_col is not None:
        df["holiday"] = holiday_col
    return df


def make_fc(
    forecast_values,
    dataset_id="DS_TEST",
    series_id="TEST_SERIES_INSIGHT",
    horizon=None,
    model="LightGBM",
    has_ci=False,
    ci_spread=0.1,
    start_date="2024-03-01",
):
    h = horizon if horizon is not None else len(forecast_values)
    dates = [
        (pd.Timestamp(start_date) + pd.Timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(len(forecast_values))
    ]
    lower = [v * (1.0 - ci_spread) for v in forecast_values] if has_ci else None
    upper = [v * (1.0 + ci_spread) for v in forecast_values] if has_ci else None
    return ForecastResult(
        dataset_id=dataset_id,
        series_id=series_id,
        model=model,
        forecast=forecast_values,
        lower_bound=lower,
        upper_bound=upper,
        dates=dates,
        forecast_horizon=h,
        notes=["Test forecast."],
    )


BASIC_MAPPING = {"date": "date", "series_id": "series_id", "target": "target"}
PRICE_MAPPING = {**BASIC_MAPPING, "optional": {"price": "price"}}
HOLIDAY_MAPPING = {**BASIC_MAPPING, "optional": {"holiday": "holiday"}}


def _make_m5_df(store_id, series_id, n=60, baseline=1.5, price=None, holiday=None):
    rng = np.random.default_rng(42)
    dates = pd.date_range("2015-10-14", periods=n, freq="D")
    df = pd.DataFrame({
        "date": dates,
        "series_id": series_id,
        # Small noise so models don't raise "constant series" errors
        "target": np.maximum(0, rng.normal(loc=baseline, scale=max(0.3, baseline * 0.1), size=n)),
        "store_id": store_id,
        "item_id": "HOBBIES_1_001",
        "category": "HOBBIES",
    })
    if price is not None:
        df["price"] = price
    if holiday is not None:
        df["holiday"] = holiday
    return df



# ===========================================================================
# 1. PRICE: Missing vs genuine zero vs genuine non-zero
# ===========================================================================

def test_price_all_nan_reports_unavailable():
    df = make_hist_df(price_col=[float("nan")] * 60)
    fc = make_fc([100.0] * 28, horizon=28)
    ins = BusinessInsightEngine.generate_insights(fc, df, PRICE_MAPPING)
    ctx = ins.optional_feature_context
    assert ctx is not None and "price" in ctx
    assert ctx["price"]["available"] is False
    assert ctx["price"]["recent_avg_price"] is None
    assert "unavailable" in ctx["price"]["insight"].lower()


def test_price_all_zero_reports_unavailable():
    df = make_hist_df(price_col=[0.0] * 60)
    fc = make_fc([100.0] * 28, horizon=28)
    ins = BusinessInsightEngine.generate_insights(fc, df, PRICE_MAPPING)
    ctx = ins.optional_feature_context
    assert ctx is not None and "price" in ctx
    assert ctx["price"]["available"] is False
    assert ctx["price"]["recent_avg_price"] is None


def test_price_genuine_nonzero_reports_available():
    prices = [8.27] * 60
    df = make_hist_df(price_col=prices)
    fc = make_fc([100.0] * 28, horizon=28)
    ins = BusinessInsightEngine.generate_insights(fc, df, PRICE_MAPPING)
    ctx = ins.optional_feature_context
    assert ctx is not None and "price" in ctx
    assert ctx["price"]["available"] is True
    assert abs(ctx["price"]["recent_avg_price"] - 8.27) < 0.01
    assert "$8.27" in ctx["price"]["insight"]


def test_price_mixed_nan_and_nonzero_reports_available():
    prices = [float("nan")] * 30 + [5.0] * 30
    df = make_hist_df(price_col=prices)
    fc = make_fc([100.0] * 28, horizon=28)
    ins = BusinessInsightEngine.generate_insights(fc, df, PRICE_MAPPING)
    ctx = ins.optional_feature_context
    assert ctx is not None and "price" in ctx
    assert ctx["price"]["available"] is True
    assert ctx["price"]["recent_avg_price"] == 5.0


def test_no_price_column_no_price_insight():
    df = make_hist_df()
    fc = make_fc([100.0] * 28, horizon=28)
    ins = BusinessInsightEngine.generate_insights(fc, df, BASIC_MAPPING)
    assert ins.optional_feature_context is None or "price" not in (ins.optional_feature_context or {})


def test_price_insight_no_promo_claim_without_promo_column():
    """Price insight must NOT mention promotional adjustments when no promotion column is mapped."""
    df = make_hist_df(price_col=[8.33] * 60)
    fc = make_fc([100.0] * 28, horizon=28)
    ins = BusinessInsightEngine.generate_insights(fc, df, PRICE_MAPPING)  # no promotion key
    ctx = ins.optional_feature_context["price"]
    assert ctx["available"] is True
    assert ctx["promotion_available"] is False
    insight = ctx["insight"].lower()
    # Must NOT make promotional claims
    assert "promotional price adjustment" not in insight
    assert "alongside promotional" not in insight
    # Must mention that promotion info is unavailable
    assert "promotion information unavailable" in insight


def test_price_insight_with_promo_column_no_unavailable_suffix():
    """When a promotion column IS mapped, no 'promotion unavailable' suffix should appear."""
    df = make_hist_df(price_col=[8.33] * 60)
    df["promo"] = [1 if i % 7 == 0 else 0 for i in range(len(df))]
    fc = make_fc([100.0] * 28, horizon=28)
    mapping_with_promo = {**PRICE_MAPPING, "optional": {"price": "price", "promotion": "promo"}}
    ins = BusinessInsightEngine.generate_insights(fc, df, mapping_with_promo)
    ctx = ins.optional_feature_context["price"]
    assert ctx["promotion_available"] is True
    assert "promotion information unavailable" not in ctx["insight"].lower()


# ===========================================================================
# 2. HOLIDAY: No events vs genuine events
# ===========================================================================

def test_holiday_all_empty_reports_unavailable():
    df = make_hist_df(holiday_col=[""] * 60)
    fc = make_fc([100.0] * 28, horizon=28)
    ins = BusinessInsightEngine.generate_insights(fc, df, HOLIDAY_MAPPING)
    ctx = ins.optional_feature_context
    assert ctx is not None and "holiday" in ctx
    assert ctx["holiday"]["available"] is False
    assert ctx["holiday"]["events_detected"] == 0


def test_holiday_all_nan_reports_unavailable():
    df = make_hist_df(holiday_col=[float("nan")] * 60)
    fc = make_fc([100.0] * 28, horizon=28)
    ins = BusinessInsightEngine.generate_insights(fc, df, HOLIDAY_MAPPING)
    ctx = ins.optional_feature_context
    assert ctx["holiday"]["available"] is False


def test_holiday_none_strings_reports_unavailable():
    df = make_hist_df(holiday_col=(["none", "nan", "", "None", "NaN"] * 12)[:60])
    fc = make_fc([100.0] * 28, horizon=28)
    ins = BusinessInsightEngine.generate_insights(fc, df, HOLIDAY_MAPPING)
    assert ins.optional_feature_context["holiday"]["available"] is False


def test_holiday_genuine_events_reports_available():
    events = ([""] * 57 + ["Christmas", "New Year", "Thanksgiving"])[:60]
    df = make_hist_df(holiday_col=events)
    fc = make_fc([100.0] * 28, horizon=28)
    ins = BusinessInsightEngine.generate_insights(fc, df, HOLIDAY_MAPPING)
    ctx = ins.optional_feature_context
    assert ctx["holiday"]["available"] is True
    assert ctx["holiday"]["events_detected"] == 3
    assert "Christmas" in ctx["holiday"]["event_names"]


def test_holiday_insight_no_causal_claim():
    events = ([""] * 57 + ["Christmas", "New Year", "Thanksgiving"])[:60]
    df = make_hist_df(holiday_col=events)
    fc = make_fc([100.0] * 28, horizon=28)
    ins = BusinessInsightEngine.generate_insights(fc, df, HOLIDAY_MAPPING)
    insight_text = ins.optional_feature_context["holiday"]["insight"].lower()
    assert "caused" not in insight_text
    assert "demand fluctuations coincide" not in insight_text


def test_holiday_unknown_placeholder_treated_as_absent():
    """'unknown', 'na', 'n/a' values must be excluded like empty strings."""
    df = make_hist_df(holiday_col=(["unknown", "Unknown", "na", "N/A", "n/a"] * 12)[:60])
    fc = make_fc([100.0] * 28, horizon=28)
    ins = BusinessInsightEngine.generate_insights(fc, df, HOLIDAY_MAPPING)
    assert ins.optional_feature_context["holiday"]["available"] is False


def test_holiday_event_records_vs_unique_types():
    """event_records counts total rows; events_detected counts unique types."""
    # 3 unique types, repeated to produce 6 total genuine records
    events = ([""] * 54 + ["Christmas", "Christmas", "Thanksgiving", "Thanksgiving", "New Year", "New Year"])[:60]
    df = make_hist_df(holiday_col=events)
    fc = make_fc([100.0] * 28, horizon=28)
    ins = BusinessInsightEngine.generate_insights(fc, df, HOLIDAY_MAPPING)
    ctx = ins.optional_feature_context["holiday"]
    assert ctx["available"] is True
    assert ctx["events_detected"] == 3   # unique types
    assert ctx["event_records"] == 6     # total genuine records
    # Insight text must reflect the full unique type count, not just 3 names
    assert "3 unique" in ctx["insight"]
    assert "6 observation" in ctx["insight"]
    # When unique_type_count <= 5, no 'and N more' suffix needed; all names shown
    assert "e.g." in ctx["insight"]
    # event_names array must contain all 3 unique types (up to 10)
    assert set(ctx["event_names"]) == {"Christmas", "Thanksgiving", "New Year"}


def test_holiday_insight_named_count_matches_events_detected():
    """Regression: 'N unique types (name1, name2, name3)' where N>5 must say
    'and M more' so the named count never implies N == 3.
    This was the bug: 16 unique types listed as only 3 names in the insight text."""
    # 8 unique event types, each appearing exactly once (records == unique types)
    unique_events = [
        "Halloween", "VeteransDay", "Thanksgiving", "Christmas",
        "NewYear", "MartinLutherKingDay", "ValentinesDay", "SuperBowl",
    ]
    events = [""] * (60 - len(unique_events)) + unique_events
    df = make_hist_df(holiday_col=events)
    fc = make_fc([100.0] * 28, horizon=28)
    ins = BusinessInsightEngine.generate_insights(fc, df, HOLIDAY_MAPPING)
    ctx = ins.optional_feature_context["holiday"]
    assert ctx["available"] is True
    assert ctx["events_detected"] == 8
    assert ctx["event_records"] == 8
    # Insight must say '8 unique' and include 'and 3 more' (5 shown + 3 remaining)
    assert "8 unique" in ctx["insight"]
    assert "and 3 more" in ctx["insight"]
    # Must NOT show all 8 names inline without the '... more' suffix
    # (would be misleading if it showed only 3 of 8)
    assert "e.g." in ctx["insight"]
    # event_names array should have up to 8 (all of them, since 8 <= 10)
    assert len(ctx["event_names"]) == 8


def test_holiday_insight_few_types_no_and_more():
    """When unique types <= 5, no 'and N more' suffix; all names listed directly."""
    events = [""] * 57 + ["Christmas", "NewYear", "Thanksgiving"]
    df = make_hist_df(holiday_col=events)
    fc = make_fc([100.0] * 28, horizon=28)
    ins = BusinessInsightEngine.generate_insights(fc, df, HOLIDAY_MAPPING)
    ctx = ins.optional_feature_context["holiday"]
    assert ctx["available"] is True
    assert "and" not in ctx["insight"].split("e.g.")[1].split(")")[0].lower() or \
           "more" not in ctx["insight"].split("e.g.")[1].split(")")[0].lower()
    # All 3 names should appear in event_names
    for name in ["Christmas", "NewYear", "Thanksgiving"]:
        assert name in ctx["event_names"]

# ===========================================================================
# 3. FORECAST DATES WITHIN HORIZON
# ===========================================================================

def _assert_dates_within_horizon(forecast_values, horizon, start_date):
    fc = make_fc(forecast_values, horizon=horizon, start_date=start_date)
    df = make_hist_df(n_days=60, baseline=100.0)
    ins = BusinessInsightEngine.generate_insights(fc, df, BASIC_MAPPING)
    outlook = ins.demand_outlook
    end_date = (pd.Timestamp(start_date) + pd.Timedelta(days=horizon - 1)).strftime("%Y-%m-%d")
    assert start_date <= outlook.expected_peak["date"] <= end_date, (
        f"Peak {outlook.expected_peak['date']} outside [{start_date}, {end_date}]"
    )
    assert start_date <= outlook.expected_low["date"] <= end_date, (
        f"Trough {outlook.expected_low['date']} outside [{start_date}, {end_date}]"
    )
    assert 1 <= outlook.expected_peak["day_index"] <= horizon
    assert 1 <= outlook.expected_low["day_index"] <= horizon


def test_peak_trough_within_7d_horizon():
    _assert_dates_within_horizon([5, 10, 3, 7, 2, 9, 4], horizon=7, start_date="2016-04-25")


def test_peak_trough_within_28d_horizon():
    values = [3.0] * 28 + [0.5] * 10
    _assert_dates_within_horizon(values, horizon=28, start_date="2016-04-25")
    fc = make_fc(values, horizon=28, start_date="2016-04-25")
    ins = BusinessInsightEngine.generate_insights(fc, make_hist_df(baseline=100.0), BASIC_MAPPING)
    assert ins.demand_outlook.expected_low["date"] <= "2016-05-22", (
        "Trough must not fall after 2016-05-22 for 28D starting 2016-04-25"
    )


def test_peak_trough_within_90d_horizon():
    _assert_dates_within_horizon(list(range(1, 91)), horizon=90, start_date="2016-04-25")


def test_forecast_sliced_to_horizon_length():
    values = [100.0] * 28 + [1.0] * 30
    fc = make_fc(values, horizon=28, start_date="2024-01-01")
    ins = BusinessInsightEngine.generate_insights(fc, make_hist_df(baseline=50.0), BASIC_MAPPING)
    assert ins.demand_outlook.expected_low["value"] == 100.0


def test_horizon_insights_peak_dates_within_respective_horizons_for_90d_forecast():
    """
    Regression: When selected forecast is 90 days, 7D and 28D cards must calculate
    peak values and dates strictly from their respective 7-day and 28-day slices.
    A peak occurring on day 80 (e.g. 2026-01-24) must NOT leak into the 7D or 28D cards.
    """
    # 90 forecast values: days 1-7 peak at 10.0 (day 3), days 1-28 peak at 15.0 (day 20), day 80 peaks at 25.22
    values = [5.0] * 90
    values[2] = 10.0   # day 3 (within 7D)
    values[19] = 15.0  # day 20 (within 28D)
    values[79] = 25.22 # day 80 (only in 90D)

    start_date = "2025-10-28"
    fc = make_fc(values, horizon=90, start_date=start_date)
    ins = BusinessInsightEngine.generate_insights(fc, make_hist_df(baseline=5.0), BASIC_MAPPING)

    # 1. Main Demand Outlook is 90D: peak is 25.22 on day 80 (2026-01-15)
    day80_date = (pd.Timestamp(start_date) + pd.Timedelta(days=79)).strftime("%Y-%m-%d")
    assert ins.demand_outlook.expected_peak["value"] == 25.22
    assert ins.demand_outlook.expected_peak["date"] == day80_date

    # 2. 7D card must have peak of 10.0 on day 3, NOT 25.22 on day 80
    day3_date = (pd.Timestamp(start_date) + pd.Timedelta(days=2)).strftime("%Y-%m-%d")
    end_7d_date = (pd.Timestamp(start_date) + pd.Timedelta(days=6)).strftime("%Y-%m-%d")
    assert "10.0" in ins.horizon_insights["7D"]
    assert day3_date in ins.horizon_insights["7D"]
    assert "25.22" not in ins.horizon_insights["7D"]
    assert day80_date not in ins.horizon_insights["7D"]
    assert f"window: {start_date} to {end_7d_date}" in ins.horizon_insights["7D"]

    # 3. 28D card must have peak of 15.0 on day 20, NOT 25.22 on day 80
    day20_date = (pd.Timestamp(start_date) + pd.Timedelta(days=19)).strftime("%Y-%m-%d")
    end_28d_date = (pd.Timestamp(start_date) + pd.Timedelta(days=27)).strftime("%Y-%m-%d")
    assert "15.0" in ins.horizon_insights["28D"]
    assert day20_date in ins.horizon_insights["28D"]
    assert "25.22" not in ins.horizon_insights["28D"]
    assert day80_date not in ins.horizon_insights["28D"]
    assert f"window: {start_date} to {end_28d_date}" in ins.horizon_insights["28D"]

    # 4. 90D card has peak of 25.22 on day 80
    end_90d_date = (pd.Timestamp(start_date) + pd.Timedelta(days=89)).strftime("%Y-%m-%d")
    assert "25.22" in ins.horizon_insights["90D"]
    assert day80_date in ins.horizon_insights["90D"]
    assert f"window: {start_date} to {end_90d_date}" in ins.horizon_insights["90D"]


def test_horizon_insights_when_horizon_is_28d_marks_90d_not_evaluated():
    values = [5.0] * 28
    fc = make_fc(values, horizon=28, start_date="2025-10-28")
    ins = BusinessInsightEngine.generate_insights(fc, make_hist_df(baseline=5.0), BASIC_MAPPING)

    assert "peak of" in ins.horizon_insights["7D"]
    assert "peak of" in ins.horizon_insights["28D"]
    assert "Not evaluated" in ins.horizon_insights["90D"]


def test_horizon_insights_when_horizon_is_7d_marks_28d_and_90d_not_evaluated():
    values = [5.0] * 7
    fc = make_fc(values, horizon=7, start_date="2025-10-28")
    ins = BusinessInsightEngine.generate_insights(fc, make_hist_df(baseline=5.0), BASIC_MAPPING)

    assert "peak of" in ins.horizon_insights["7D"]
    assert "Not evaluated" in ins.horizon_insights["28D"]
    assert "Not evaluated" in ins.horizon_insights["90D"]


# ===========================================================================
# 4. SCOPE & STORE SWITCHING
# ===========================================================================

def test_ca2_scope_in_insight_response():
    ds_id = "DS_SCOPE_CA2"
    df = _make_m5_df("CA_2", "HOBBIES_1_001_CA_2")
    save_dataset(ds_id, df, "m5_ca2.csv")
    res = client.post("/api/insights/generate", json={
        "dataset_id": ds_id, "series_id": "HOBBIES_1_001_CA_2",
        "store_id": "CA_2", "model": "lightgbm", "horizon": 28,
    })
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["series_id"] == "HOBBIES_1_001_CA_2"
    assert data["store_id"] == "CA_2"
    assert data["scope"]["store_id"] == "CA_2"


def test_ca3_scope_in_insight_response():
    ds_id = "DS_SCOPE_CA3"
    df = _make_m5_df("CA_3", "HOBBIES_1_001_CA_3")
    save_dataset(ds_id, df, "m5_ca3.csv")
    res = client.post("/api/insights/generate", json={
        "dataset_id": ds_id, "series_id": "HOBBIES_1_001_CA_3",
        "store_id": "CA_3", "model": "lightgbm", "horizon": 28,
    })
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["series_id"] == "HOBBIES_1_001_CA_3"
    assert data["store_id"] == "CA_3"


def test_switching_ca2_to_ca3_returns_different_series():
    ds_id = "DS_SWITCH_CA23"
    combined = pd.concat([
        _make_m5_df("CA_2", "HOBBIES_1_001_CA_2", baseline=2.0),
        _make_m5_df("CA_3", "HOBBIES_1_001_CA_3", baseline=3.0),
    ], ignore_index=True)
    save_dataset(ds_id, combined, "m5_switch.csv")
    res2 = client.post("/api/insights/generate", json={"dataset_id": ds_id, "store_id": "CA_2", "model": "lightgbm", "horizon": 7})
    res3 = client.post("/api/insights/generate", json={"dataset_id": ds_id, "store_id": "CA_3", "model": "lightgbm", "horizon": 7})
    assert res2.status_code == 200
    assert res3.status_code == 200
    assert res2.json()["series_id"] != res3.json()["series_id"]


# ===========================================================================
# 5. CACHE: Stale-result prevention
# ===========================================================================

def test_cache_strict_store_id_match():
    INSIGHTS_CACHE.clear()
    fc1 = make_fc([5.0] * 28, dataset_id="DS_CACHE_STRICT", series_id="HOBBIES_1_001_CA_1", horizon=28)
    BusinessInsightEngine.generate_insights(fc1, _make_m5_df("CA_1", "HOBBIES_1_001_CA_1"), BASIC_MAPPING, store_id="CA_1")
    result = BusinessInsightEngine.get_cached_insights(
        dataset_id="DS_CACHE_STRICT", series_id="HOBBIES_1_001_CA_2", horizon=28, store_id="CA_2",
    )
    assert result is None, "CA_1 cache must not satisfy CA_2 lookup"


def test_cache_no_store_tag_not_returned_for_scoped():
    INSIGHTS_CACHE.clear()
    fc = make_fc([5.0] * 28, dataset_id="DS_CACHE_NOTAG", series_id="TEST_SERIES_INSIGHT", horizon=28)
    BusinessInsightEngine.generate_insights(fc, make_hist_df(), BASIC_MAPPING)
    result = BusinessInsightEngine.get_cached_insights(
        dataset_id="DS_CACHE_NOTAG", series_id="TEST_SERIES_INSIGHT", horizon=28, store_id="CA_2",
    )
    assert result is None


def test_cache_returns_correct_store_entry():
    INSIGHTS_CACHE.clear()
    fc = make_fc([5.0] * 28, dataset_id="DS_CACHE_HIT", series_id="HOBBIES_1_001_CA_2", horizon=28)
    BusinessInsightEngine.generate_insights(fc, _make_m5_df("CA_2", "HOBBIES_1_001_CA_2"), BASIC_MAPPING, store_id="CA_2")
    result = BusinessInsightEngine.get_cached_insights(
        dataset_id="DS_CACHE_HIT", series_id="HOBBIES_1_001_CA_2", horizon=28, store_id="CA_2",
    )
    assert result is not None
    assert result["store_id"] == "CA_2"


# ===========================================================================
# 6. UNAVAILABLE DATA STATES
# ===========================================================================

def test_optional_context_none_when_no_optionals():
    ins = BusinessInsightEngine.generate_insights(make_fc([100.0] * 28, horizon=28), make_hist_df(), BASIC_MAPPING)
    assert ins.optional_feature_context is None


def test_strategic_demand_planning_never_empty():
    for val in [130.0, 80.0, 103.0]:
        ins = BusinessInsightEngine.generate_insights(make_fc([val] * 28, horizon=28), make_hist_df(), BASIC_MAPPING)
        dp = ins.demand_planning
        assert dp and dp.get("explanation") and dp.get("state") and dp.get("action")


# ===========================================================================
# 7. RETAINED CORE TESTS
# ===========================================================================

def test_demand_increase_insight():
    ins = BusinessInsightEngine.generate_insights(make_fc([125.0] * 28, horizon=28), make_hist_df(), BASIC_MAPPING)
    assert ins.demand_outlook.demand_direction == "INCREASING"
    assert ins.demand_outlook.expected_change_pct == 25.0
    assert ins.inventory_recommendation.recommendation == "CONSIDER STOCKING UP"


def test_stable_demand_insight():
    ins = BusinessInsightEngine.generate_insights(make_fc([102.0] * 28, horizon=28), make_hist_df(), BASIC_MAPPING)
    assert ins.demand_outlook.demand_direction == "STABLE"


def test_demand_decrease_insight():
    ins = BusinessInsightEngine.generate_insights(make_fc([80.0] * 28, horizon=28), make_hist_df(), BASIC_MAPPING)
    assert ins.demand_outlook.demand_direction == "DECREASING"


def test_evidence_values_match_forecast_calculations():
    hist_df = make_hist_df(baseline=50.0)
    fc = make_fc([40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0], horizon=7)
    ins = BusinessInsightEngine.generate_insights(fc, hist_df, BASIC_MAPPING)
    ev = ins.inventory_recommendation.evidence
    assert ev["recent_average"] == 50.0
    assert ev["forecast_average"] == 70.0
    assert ev["expected_peak"]["value"] == 100.0
    assert ev["expected_low"]["value"] == 40.0
    assert ev["horizon"] == 7


def test_monitoring_status_healthy():
    report = MonitoringTracker.evaluate_monitoring_status("DS_HEALTHY", backtest_summary={
        "models_evaluated": ["lightgbm"],
        "series_details": [{"series_id": "S1", "folds": [
            {"fold": 1, "mape": 10.0, "status": "SUCCESS"},
            {"fold": 2, "mape": 10.5, "status": "SUCCESS"}
        ]}]
    })
    assert report.status == "HEALTHY"
    assert report.is_alert is False


def test_accuracy_degradation_alert():
    report = MonitoringTracker.evaluate_monitoring_status("DS_DRIFT", backtest_summary={
        "models_evaluated": ["arima"],
        "series_details": [{"series_id": "S1", "folds": [
            {"fold": 1, "mape": 10.0, "status": "SUCCESS"},
            {"fold": 2, "mape": 15.0, "status": "SUCCESS"}
        ]}]
    })
    assert report.status == "ACCURACY DRIFT"
    assert report.is_alert is True


def test_insights_api_endpoint_smoke():
    ds_id = "DS_API_SMOKE"
    df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=90, freq="D"),
        "series_id": "SERIES_SMOKE",
        "target": np.random.uniform(50, 100, 90)
    })
    save_dataset(ds_id, df, "smoke.csv")
    res = client.post("/api/insights/generate", json={
        "dataset_id": ds_id, "series_id": "SERIES_SMOKE", "model": "arima", "horizon": 28,
    })
    assert res.status_code == 200, res.text
    assert res.json()["series_id"] == "SERIES_SMOKE"


# ===========================================================================
# 8. REGRESSION TESTS: SERIES-SPECIFIC FORECAST-WINDOW ALIGNMENT & HORIZONS
# ===========================================================================

def test_series_specific_historical_cutoffs_and_windows_edge_case():
    """
    Test that two series in the same dataset with different historical cutoffs
    generate distinct, non-overlapping out-of-sample forecast windows:
    - STORE_A_SKU_001 valid target cutoff is 2025-11-06 (NaN target on 2025-11-07 and invalid date).
      Forecast must start 2025-11-07!
    - STORE_B_SKU_002 valid target cutoff is 2025-11-08.
      Forecast must start 2025-11-09!
    """
    from app.data.cleaner import clean_canonical_dataset
    from app.data.loader import detect_candidate_columns

    ds_id = "DS_EDGE_CASE_TEST"
    # Create raw dataframe mirroring 03_edge_case_retail.csv
    dates_a = pd.date_range("2025-01-01", "2025-11-06", freq="D")
    df_a = pd.DataFrame({
        "date": [d.strftime("%Y-%m-%d") for d in dates_a],
        "series_id": "STORE_A_SKU_001",
        "target": np.random.uniform(10, 20, len(dates_a)),
        "store_id": "STORE_A",
        "category": "Beverages",
    })
    # Add corrupted rows for STORE_A
    extra_a = pd.DataFrame([
        {"date": "2025-11-07", "series_id": "STORE_A_SKU_001", "target": np.nan, "store_id": "STORE_A", "category": "Beverages"},
        {"date": "not-a-date", "series_id": "STORE_A_SKU_001", "target": 15.0, "store_id": "STORE_A", "category": "Beverages"},
    ])

    dates_b = pd.date_range("2025-01-01", "2025-11-08", freq="D")
    df_b = pd.DataFrame({
        "date": [d.strftime("%Y-%m-%d") for d in dates_b],
        "series_id": "STORE_B_SKU_002",
        "target": np.random.uniform(20, 30, len(dates_b)),
        "store_id": "STORE_B",
        "category": "Snacks",
    })

    full_df = pd.concat([df_a, extra_a, df_b], ignore_index=True)
    mapping = detect_candidate_columns(list(full_df.columns))
    save_dataset(ds_id, full_df, "03_edge_case_retail.csv")
    clean_canonical_dataset(ds_id, full_df, mapping)

    # 1. Generate 7D insights for STORE_A_SKU_001
    res_a_7d = client.get(f"/api/insights/{ds_id}/series/STORE_A_SKU_001?horizon=7&model=arima&store_id=STORE_A")
    assert res_a_7d.status_code == 200, res_a_7d.text
    data_a = res_a_7d.json()

    outlook_a = data_a["demand_outlook"]
    # 7D forecast period must be exactly 2025-11-07 to 2025-11-13 (7 future days starting after 2025-11-06)
    assert outlook_a["forecast_period"] == "2025-11-07 to 2025-11-13"
    assert data_a["inventory_recommendation"]["planning_period"] == "2025-11-07 to 2025-11-13"
    assert data_a["staffing_recommendation"]["planning_period"] == "2025-11-07 to 2025-11-13"
    assert data_a["procurement_recommendation"]["planning_period"] == "2025-11-07 to 2025-11-13"
    # Peak and trough dates must belong strictly to this window
    assert "2025-11-07" <= outlook_a["expected_peak"]["date"] <= "2025-11-13"
    assert "2025-11-07" <= outlook_a["expected_low"]["date"] <= "2025-11-13"

    # 2. Generate 7D insights for STORE_B_SKU_002
    res_b_7d = client.get(f"/api/insights/{ds_id}/series/STORE_B_SKU_002?horizon=7&model=arima&store_id=STORE_B")
    assert res_b_7d.status_code == 200, res_b_7d.text
    data_b = res_b_7d.json()

    outlook_b = data_b["demand_outlook"]
    # 7D forecast period must be exactly 2025-11-09 to 2025-11-15 (7 future days starting after 2025-11-08)
    assert outlook_b["forecast_period"] == "2025-11-09 to 2025-11-15"
    assert "2025-11-09" <= outlook_b["expected_peak"]["date"] <= "2025-11-15"
    assert "2025-11-09" <= outlook_b["expected_low"]["date"] <= "2025-11-15"


def test_forecast_horizons_7d_28d_90d_counts_and_boundaries():
    """
    Test 7D, 28D, and 90D horizons for exact timestamp count and boundary dates.
    For latest valid date 2025-11-08:
    - 7D: 2025-11-09 through 2025-11-15 (7 days)
    - 28D: 2025-11-09 through 2025-12-06 (28 days)
    - 90D: 2025-11-09 through 2026-02-06 (90 days)
    """
    from app.data.cleaner import clean_canonical_dataset
    from app.data.loader import detect_candidate_columns

    ds_id = "DS_HORIZONS_BOUNDARY_TEST"
    dates = pd.date_range("2025-01-01", "2025-11-08", freq="D")
    df = pd.DataFrame({
        "date": [d.strftime("%Y-%m-%d") for d in dates],
        "series_id": "SERIES_CUTOFF_TEST",
        "target": np.random.uniform(10, 20, len(dates)),
    })
    mapping = detect_candidate_columns(list(df.columns))
    save_dataset(ds_id, df, "horizon_test.csv")
    clean_canonical_dataset(ds_id, df, mapping)

    # Test 7D
    res7 = client.post("/api/insights/generate", json={
        "dataset_id": ds_id, "series_id": "SERIES_CUTOFF_TEST", "model": "arima", "horizon": 7
    })
    assert res7.status_code == 200
    d7 = res7.json()
    assert d7["demand_outlook"]["forecast_period"] == "2025-11-09 to 2025-11-15"
    assert "2025-11-09" <= d7["demand_outlook"]["expected_peak"]["date"] <= "2025-11-15"
    assert "2025-11-09" <= d7["demand_outlook"]["expected_low"]["date"] <= "2025-11-15"

    # Test 28D
    res28 = client.post("/api/insights/generate", json={
        "dataset_id": ds_id, "series_id": "SERIES_CUTOFF_TEST", "model": "arima", "horizon": 28
    })
    assert res28.status_code == 200
    d28 = res28.json()
    assert d28["demand_outlook"]["forecast_period"] == "2025-11-09 to 2025-12-06"
    assert "2025-11-09" <= d28["demand_outlook"]["expected_peak"]["date"] <= "2025-12-06"
    assert "2025-11-09" <= d28["demand_outlook"]["expected_low"]["date"] <= "2025-12-06"

    # Test 90D
    res90 = client.post("/api/insights/generate", json={
        "dataset_id": ds_id, "series_id": "SERIES_CUTOFF_TEST", "model": "arima", "horizon": 90
    })
    assert res90.status_code == 200
    d90 = res90.json()
    assert d90["demand_outlook"]["forecast_period"] == "2025-11-09 to 2026-02-06"
    assert "2025-11-09" <= d90["demand_outlook"]["expected_peak"]["date"] <= "2026-02-06"
    assert "2025-11-09" <= d90["demand_outlook"]["expected_low"]["date"] <= "2026-02-06"


def test_forecast_no_overlap_with_historical_dates():
    """Ensure no forecast dates overlap with any training observation dates."""
    from app.data.cleaner import clean_canonical_dataset
    from app.data.loader import detect_candidate_columns

    ds_id = "DS_NO_OVERLAP_TEST"
    dates = pd.date_range("2025-01-01", "2025-05-31", freq="D")
    hist_date_strs = set([d.strftime("%Y-%m-%d") for d in dates])
    df = pd.DataFrame({
        "date": [d.strftime("%Y-%m-%d") for d in dates],
        "series_id": "SERIES_OVERLAP_TEST",
        "target": np.random.uniform(50, 60, len(dates)),
    })
    mapping = detect_candidate_columns(list(df.columns))
    save_dataset(ds_id, df, "overlap_test.csv")
    clean_canonical_dataset(ds_id, df, mapping)

    res = client.post("/api/forecast/generate", json={
        "dataset_id": ds_id, "series_id": "SERIES_OVERLAP_TEST", "model": "arima", "horizon": 28
    })
    assert res.status_code == 200
    fc_dates = res.json()["dates"]
    assert len(fc_dates) == 28
    # Zero intersection with history
    assert len(set(fc_dates).intersection(hist_date_strs)) == 0
    # First forecast date is strictly the day after the last history date (2025-06-01)
    assert fc_dates[0] == "2025-06-01"
    assert fc_dates[-1] == "2025-06-28"


def test_monitoring_insufficient_evidence_when_single_fold_or_no_data():
    """Verify that MonitoringTracker never returns HEALTHY without at least 2 distinct evaluation folds."""
    # 0 folds / no evaluations
    rep_empty = MonitoringTracker.evaluate_monitoring_status("DS_EMPTY", backtest_summary={
        "models_evaluated": ["arima"],
        "series_details": []
    })
    assert rep_empty.status == "INSUFFICIENT DATA"
    assert rep_empty.mape_drift_pct is None
    assert rep_empty.is_alert is False

    # 1 fold only -> not enough to measure fold-over-fold degradation
    rep_single = MonitoringTracker.evaluate_monitoring_status("DS_SINGLE", backtest_summary={
        "models_evaluated": ["arima"],
        "series_details": [{"series_id": "S1", "folds": [
            {"fold": 1, "mape": 12.0, "status": "SUCCESS"}
        ]}]
    })
    assert rep_single.status == "INSUFFICIENT DATA"
    assert rep_single.mape_drift_pct is None
    assert rep_single.is_alert is False


def test_monitoring_scope_filtering_and_not_evaluated_state():
    """Verify that monitoring isolates specific series, model, and horizon scope."""
    backtest_data = {
        "models_evaluated": ["arima", "lightgbm"],
        "best_per_horizon": {
            "28D": {"best_model": "lightgbm", "mape": 10.0}
        },
        "series_details": [
            {
                "series_id": "SERIES_A",
                "model": "lightgbm",
                "horizon": 28,
                "folds": [
                    {"fold": 1, "mape": 8.0, "status": "SUCCESS"},
                    {"fold": 2, "mape": 8.2, "status": "SUCCESS"},
                ]
            },
            {
                "series_id": "SERIES_B",
                "model": "arima",
                "horizon": 28,
                "folds": [
                    {"fold": 1, "mape": 10.0, "status": "SUCCESS"},
                    {"fold": 2, "mape": 14.0, "status": "SUCCESS"},  # 40% drift!
                ]
            }
        ]
    }

    # Scoped to SERIES_A with lightgbm (healthy)
    rep_a = MonitoringTracker.evaluate_monitoring_status(
        "DS_MULTI_SCOPE",
        backtest_summary=backtest_data,
        series_id="SERIES_A",
        model="lightgbm",
        horizon=28
    )
    assert rep_a.status == "HEALTHY"
    assert rep_a.mape_drift_pct == 2.5
    assert rep_a.is_alert is False

    # Scoped to SERIES_B with arima (accuracy drift alert)
    rep_b = MonitoringTracker.evaluate_monitoring_status(
        "DS_MULTI_SCOPE",
        backtest_summary=backtest_data,
        series_id="SERIES_B",
        model="arima",
        horizon=28
    )
    assert rep_b.status == "ACCURACY DRIFT"
    assert rep_b.mape_drift_pct == 40.0
    assert rep_b.is_alert is True

    # Scoped to un-evaluated series -> NOT EVALUATED (not fabricated healthy!)
    rep_unevaluated = MonitoringTracker.evaluate_monitoring_status(
        "DS_MULTI_SCOPE",
        backtest_summary=backtest_data,
        series_id="SERIES_C",
        model="arima",
        horizon=28
    )
    assert rep_unevaluated.status == "NOT EVALUATED"
    assert rep_unevaluated.mape_drift_pct is None


def test_monitoring_endpoint_query_params():
    """Verify GET /api/monitoring/{dataset_id} supports and respects scope query params."""
    ds_id = "DS_API_MONITOR_TEST"
    df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=90, freq="D"),
        "series_id": "SERIES_MTEST",
        "target": np.random.uniform(50, 100, 90)
    })
    save_dataset(ds_id, df, "mtest.csv")

    res = client.get(f"/api/monitoring/{ds_id}?series_id=SERIES_MTEST&model=arima&horizon=28")
    assert res.status_code == 200
    data = res.json()
    assert data["dataset_id"] == ds_id
    assert data["series_id"] == "SERIES_MTEST"
    assert data["horizon"] == 28
    # Initially no backtest run -> INSUFFICIENT DATA or NOT EVALUATED, never fake HEALTHY
    assert data["status"] in ["INSUFFICIENT DATA", "NOT EVALUATED"]



