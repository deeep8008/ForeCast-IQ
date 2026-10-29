"""
Phase 5 LightGBM Forecasting Model Comprehensive Test Suite
ForecastIQ Backend
"""
import io
import pytest
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient
from app.main import app
from app.models.lightgbm import LightgbmForecaster
from app.data.schema import ForecastResult, ForecastRequest, LightgbmConfig

client = TestClient(app)


def make_synthetic_series(n_days=120, trend=0.1, seasonality=5.0, noise_scale=1.0):
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=n_days, freq="D")
    t = np.arange(n_days)
    seas = seasonality * np.sin(2 * np.pi * t / 7.0)
    noise = np.random.normal(0, noise_scale, n_days)
    target = np.maximum(5.0, 20.0 + trend * t + seas + noise)
    return pd.DataFrame({
        "date": dates,
        "series_id": "SERIES_LGBM_1",
        "target": target
    })


# 1. LightGBM Initialization and Hyperparameters
def test_lightgbm_initialization_and_params():
    forecaster = LightgbmForecaster(
        n_estimators=50,
        learning_rate=0.08,
        num_leaves=15,
        max_depth=5,
        subsample=0.7,
        random_state=123
    )
    assert forecaster.model_name == "LightGBM"
    assert forecaster.n_estimators == 50
    assert forecaster.learning_rate == 0.08
    assert forecaster.num_leaves == 15
    assert forecaster.max_depth == 5
    assert forecaster.subsample == 0.7
    assert forecaster.random_state == 123
    assert forecaster.is_fitted is False


# 2. Multi-Horizon Forecasting: 7-day, 28-day, and 90-day
def test_lightgbm_forecast_7_28_90():
    df = make_synthetic_series(n_days=150)
    forecaster = LightgbmForecaster(n_estimators=30, num_leaves=15)
    forecaster.fit(df, time_col="date", target_col="target", horizon=28)
    assert forecaster.is_fitted is True

    # 7-day forecast
    res_7 = forecaster.forecast(horizon=7, dataset_id="ds-lgbm", series_id="SERIES_LGBM_1")
    assert isinstance(res_7, ForecastResult)
    assert len(res_7.forecast) == 7
    assert len(res_7.dates) == 7
    assert len(res_7.points) == 7
    assert res_7.forecast_horizon == 7
    assert res_7.status == "SUCCESS"

    # 28-day forecast
    res_28 = forecaster.forecast(horizon=28, dataset_id="ds-lgbm", series_id="SERIES_LGBM_1")
    assert len(res_28.forecast) == 28
    assert len(res_28.dates) == 28
    assert len(res_28.points) == 28
    assert res_28.forecast_horizon == 28

    # 90-day forecast
    res_90 = forecaster.forecast(horizon=90, dataset_id="ds-lgbm", series_id="SERIES_LGBM_1")
    assert len(res_90.forecast) == 90
    assert len(res_90.dates) == 90
    assert len(res_90.points) == 90
    assert res_90.forecast_horizon == 90


# 3. Canonical ForecastResult Structure & No Fabricated Intervals
def test_lightgbm_result_structure_and_no_fake_intervals():
    df = make_synthetic_series(n_days=80)
    forecaster = LightgbmForecaster(n_estimators=20)
    forecaster.fit(df, time_col="date", target_col="target", horizon=7)
    res = forecaster.forecast(horizon=7, dataset_id="ds-lgbm-bounds", series_id="SERIES_LGBM_1")

    # Lower bound and upper bound must be None (no fake uncertainty generated)
    assert res.lower_bound is None
    assert res.upper_bound is None
    for pt in res.points:
        assert pt.lower_bound is None
        assert pt.upper_bound is None
        assert isinstance(pt.forecast, float)

    # Dates are consecutive future days
    last_hist_date = pd.to_datetime(df["date"].iloc[-1])
    expected_first_date = (last_hist_date + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    assert res.dates[0] == expected_first_date
    assert res.training_start == df["date"].iloc[0].strftime("%Y-%m-%d")
    assert res.training_end == df["date"].iloc[-1].strftime("%Y-%m-%d")
    assert res.forecast_start == res.dates[0]
    assert res.forecast_end == res.dates[-1]


# 4. Feature Usage: Lag, Rolling, and Calendar Features Present
def test_lightgbm_features_utilized():
    df = make_synthetic_series(n_days=100)
    forecaster = LightgbmForecaster(n_estimators=20)
    forecaster.fit(df, time_col="date", target_col="target", horizon=7)

    features = forecaster.feature_columns
    # Check that lag, rolling, and calendar features were engineered and used
    assert any("lag" in f for f in features), "Lag features should be in feature columns"
    assert any("rolling" in f for f in features), "Rolling features should be in feature columns"
    assert any("calendar" in f or "weekday" in f or "month" in f for f in features), "Calendar features should be present"
    # Series_id must not be a numeric feature
    assert "series_id" not in features


# 5. Leakage Protection & Recursive Forecast Projection
def test_lightgbm_recursive_forecast_rolling():
    df = make_synthetic_series(n_days=90)
    forecaster = LightgbmForecaster(n_estimators=25)
    forecaster.fit(df, time_col="date", target_col="target", horizon=28)

    # Forecasting should run without error across full horizon
    res = forecaster.forecast(horizon=28, dataset_id="ds-leak", series_id="SERIES_LGBM_1")
    # Predictions should be valid positive numbers
    for val in res.forecast:
        assert np.isfinite(val)
        assert val >= 0.0


# 6. Error Handling: Insufficient History and Constant Series
def test_lightgbm_validation_errors():
    # Insufficient history (< 35 observations for 28-day lag)
    short_df = make_synthetic_series(n_days=20)
    forecaster = LightgbmForecaster()
    with pytest.raises(ValueError, match="Not enough historical data"):
        forecaster.fit(short_df, time_col="date", target_col="target", horizon=28)

    # Constant series (zero variance)
    const_df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=60, freq="D"),
        "series_id": "S_CONST",
        "target": [10.0] * 60
    })
    with pytest.raises(ValueError, match="Series is constant"):
        forecaster.fit(const_df, time_col="date", target_col="target", horizon=7)

    # Unfitted forecast call
    unfitted = LightgbmForecaster()
    with pytest.raises(RuntimeError, match="Model must be fitted"):
        unfitted.forecast(horizon=7, dataset_id="ds", series_id="s")


# 7. Zero Target Handling (Preservation of Zero Demand)
def test_lightgbm_zero_target_handling():
    dates = pd.date_range("2024-01-01", periods=80, freq="D")
    # Intermittent demand with valid zeroes
    targets = [0.0 if i % 3 == 0 else 5.0 + (i % 5) for i in range(80)]
    df = pd.DataFrame({
        "date": dates,
        "series_id": "INTERMITTENT_1",
        "target": targets
    })
    forecaster = LightgbmForecaster(n_estimators=30)
    forecaster.fit(df, time_col="date", target_col="target", horizon=7)
    res = forecaster.forecast(horizon=7, dataset_id="ds-zeros", series_id="INTERMITTENT_1")
    assert len(res.forecast) == 7
    # All predictions non-negative
    assert all(f >= 0.0 for f in res.forecast)


# 8. Categorical Covariates Encoding
def test_lightgbm_categorical_covariates():
    df = make_synthetic_series(n_days=90)
    df["store_id"] = ["CA_1" if i % 2 == 0 else "CA_2" for i in range(len(df))]
    df["item_id"] = "FOODS_1"

    forecaster = LightgbmForecaster(n_estimators=20)
    forecaster.fit(df, time_col="date", target_col="target", horizon=14)
    res = forecaster.forecast(horizon=14, dataset_id="ds-cat", series_id="SERIES_LGBM_1")

    assert len(res.forecast) == 14
    assert res.status == "SUCCESS"


# 9. Direct API Endpoint: POST /api/forecast/lightgbm
def test_api_direct_lightgbm_endpoint():
    # Upload sample CSV first
    df = make_synthetic_series(n_days=100)
    csv_bytes = df.to_csv(index=False).encode("utf-8")

    upload_res = client.post(
        "/api/data/upload",
        files={"file": ("test_lgbm_series.csv", io.BytesIO(csv_bytes), "text/csv")}
    )
    assert upload_res.status_code == 200
    dataset_id = upload_res.json()["dataset_id"]

    # Call direct lightgbm endpoint
    res = client.post(
        f"/api/forecast/lightgbm?dataset_id={dataset_id}&series_id=SERIES_LGBM_1&horizon=28&n_estimators=50&learning_rate=0.05&num_leaves=31"
    )
    assert res.status_code == 200
    data = res.json()
    assert data["model"] == "LightGBM"
    assert data["forecast_horizon"] == 28
    assert len(data["forecast"]) == 28
    assert data["lower_bound"] is None
    assert data["upper_bound"] is None
    assert data["status"] == "SUCCESS"


# 10. Unified API Endpoint: POST /api/forecast/generate with model=lightgbm
def test_api_unified_lightgbm_routing():
    df = make_synthetic_series(n_days=100)
    csv_bytes = df.to_csv(index=False).encode("utf-8")

    upload_res = client.post(
        "/api/data/upload",
        files={"file": ("test_lgbm_unified.csv", io.BytesIO(csv_bytes), "text/csv")}
    )
    assert upload_res.status_code == 200
    dataset_id = upload_res.json()["dataset_id"]

    payload = {
        "dataset_id": dataset_id,
        "series_id": "SERIES_LGBM_1",
        "horizon": 7,
        "model": "lightgbm",
        "lightgbm_config": {
            "n_estimators": 40,
            "learning_rate": 0.06,
            "num_leaves": 25
        }
    }
    res = client.post("/api/forecast/generate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["model"] == "LightGBM"
    assert data["forecast_horizon"] == 7
    assert len(data["forecast"]) == 7
    assert len(data["points"]) == 7
