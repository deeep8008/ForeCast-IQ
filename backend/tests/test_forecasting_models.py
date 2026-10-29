"""
Phase 4 Forecasting Models Test Suite (ARIMA, SARIMA, Prophet)
ForecastIQ Backend
"""
import io
import pytest
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient
from app.main import app
from app.models.arima import ArimaForecaster
from app.models.sarima import SarimaForecaster
from app.models.prophet_model import ProphetForecaster
from app.data.schema import ForecastResult, ForecastRequest

client = TestClient(app)


# Helper: Generate deterministic daily time-series
def make_synthetic_series(n_days=100, trend=0.1, seasonality=5.0, noise_scale=1.0):
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=n_days, freq="D")
    t = np.arange(n_days)
    # Weekly seasonality
    seas = seasonality * np.sin(2 * np.pi * t / 7.0)
    noise = np.random.normal(0, noise_scale, n_days)
    target = np.maximum(5.0, 20.0 + trend * t + seas + noise)
    return pd.DataFrame({
        "date": dates,
        "series_id": "SERIES_TEST_1",
        "target": target
    })


# 1. ARIMA Model Initialization, Training, and Prediction
def test_arima_fit_and_forecast_7_28_90():
    df = make_synthetic_series(n_days=150)
    
    # 7-day horizon
    forecaster_7 = ArimaForecaster(p=1, d=1, q=1)
    forecaster_7.fit(df, time_col="date", target_col="target", horizon=7)
    res_7 = forecaster_7.forecast(horizon=7, dataset_id="ds-1", series_id="SERIES_TEST_1")

    assert isinstance(res_7, ForecastResult)
    assert len(res_7.forecast) == 7
    assert len(res_7.dates) == 7
    assert len(res_7.lower_bound) == 7
    assert len(res_7.upper_bound) == 7
    assert len(res_7.points) == 7
    assert res_7.forecast_horizon == 7
    assert res_7.status == "SUCCESS"

    # 28-day horizon
    forecaster_28 = ArimaForecaster(p=1, d=1, q=1)
    forecaster_28.fit(df, time_col="date", target_col="target", horizon=28)
    res_28 = forecaster_28.forecast(horizon=28, dataset_id="ds-1", series_id="SERIES_TEST_1")
    assert len(res_28.forecast) == 28

    # 90-day horizon
    forecaster_90 = ArimaForecaster(p=1, d=1, q=1)
    forecaster_90.fit(df, time_col="date", target_col="target", horizon=90)
    res_90 = forecaster_90.forecast(horizon=90, dataset_id="ds-1", series_id="SERIES_TEST_1")
    assert len(res_90.forecast) == 90


# 2. ARIMA Error Handling: Insufficient History, Constant Series, Missing Target
def test_arima_validation_errors():
    # Insufficient history for 28-day horizon (only 10 rows)
    short_df = make_synthetic_series(n_days=10)
    forecaster = ArimaForecaster(p=1, d=1, q=1)
    with pytest.raises(ValueError, match="Not enough historical data"):
        forecaster.fit(short_df, time_col="date", target_col="target", horizon=28)

    # Constant series (zero variance)
    const_df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=50, freq="D"),
        "series_id": "S1",
        "target": [42.0] * 50
    })
    with pytest.raises(ValueError, match="Series is constant"):
        forecaster.fit(const_df, time_col="date", target_col="target", horizon=7)

    # Missing targets
    na_df = make_synthetic_series(n_days=50)
    na_df.loc[10, "target"] = np.nan
    with pytest.raises(ValueError, match="Target contains unresolved missing values"):
        forecaster.fit(na_df, time_col="date", target_col="target", horizon=7)


# 3. SARIMA Model Initialization, Seasonal Order, and Forecast
def test_sarima_fit_and_forecast():
    df = make_synthetic_series(n_days=70)
    sarima = SarimaForecaster(order=(1, 1, 1), seasonal_order=(1, 0, 1, 7))
    sarima.fit(df, time_col="date", target_col="target", horizon=28)
    res = sarima.forecast(horizon=28, dataset_id="ds-sarima", series_id="SERIES_TEST_1")

    assert isinstance(res, ForecastResult)
    assert len(res.forecast) == 28
    assert res.components["seasonal_period"] == 7
    assert res.status == "SUCCESS"


# 4. Prophet Model Initialization, Seasonality, Components, and Forecasts
def test_prophet_fit_and_forecast_7_28():
    df = make_synthetic_series(n_days=80)
    prophet_model = ProphetForecaster(weekly_seasonality=True, yearly_seasonality=False)
    prophet_model.fit(df, time_col="date", target_col="target", horizon=28)
    res = prophet_model.forecast(horizon=28, dataset_id="ds-prophet", series_id="SERIES_TEST_1")

    assert isinstance(res, ForecastResult)
    assert len(res.forecast) == 28
    assert len(res.points) == 28
    assert res.model == "Prophet"
    assert "trend" in res.components
    assert "weekly" in res.components
    assert len(res.components["weekly"]) == 28


# 5. Prophet Future Regressor Protection (Leakage Prevention)
def test_prophet_future_regressor_protection():
    df = make_synthetic_series(n_days=50)
    df["known_holiday"] = [0] * 50

    forecaster = ProphetForecaster()
    # Fit with a future covariate
    forecaster.fit(df, time_col="date", target_col="target", horizon=7, future_covariates=["known_holiday"])

    # Attempting to forecast without providing future values for known_holiday must raise an error
    with pytest.raises(ValueError, match="future covariate values were not provided"):
        forecaster.forecast(horizon=7, dataset_id="ds-reg", series_id="SERIES_TEST_1")


# 6. Chronological Leakage Protection Test
def test_chronological_isolation():
    # Ensure forecast timestamps are strictly after the training end date
    df = make_synthetic_series(n_days=60)
    forecaster = ArimaForecaster(p=1, d=1, q=1)
    forecaster.fit(df, time_col="date", target_col="target", horizon=7)
    res = forecaster.forecast(horizon=7, dataset_id="ds-chrono", series_id="SERIES_TEST_1")

    assert res.forecast_start > res.training_end
    for pt in res.points:
        assert pt.date > res.training_end


# 7. Integration: Upload Dataset -> Clean -> Generate ARIMA / SARIMA / Prophet Forecast via API
def test_forecast_api_integration():
    # Ingest a small clean CSV
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    csv_rows = ["date,series_id,target"]
    for i, d in enumerate(dates):
        csv_rows.append(f"{d.strftime('%Y-%m-%d')},STORE_CA_ITEM_1,{20.0 + (i % 7) * 2}")
    csv_content = "\n".join(csv_rows).encode("utf-8")

    files = {"file": ("forecast_series_test.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = client.post("/api/data/upload", files=files)
    assert upload_res.status_code == 200
    dataset_id = upload_res.json()["dataset_id"]

    # 1. ARIMA Endpoint
    arima_res = client.post(
        f"/api/forecast/arima?dataset_id={dataset_id}&series_id=STORE_CA_ITEM_1&horizon=7&p=1&d=1&q=1"
    )
    assert arima_res.status_code == 200
    arima_data = arima_res.json()
    assert len(arima_data["forecast"]) == 7
    assert arima_data["series_id"] == "STORE_CA_ITEM_1"

    # 2. SARIMA Endpoint
    sarima_res = client.post(
        f"/api/forecast/sarima?dataset_id={dataset_id}&series_id=STORE_CA_ITEM_1&horizon=14&seasonal_period=7"
    )
    assert sarima_res.status_code == 200
    sarima_data = sarima_res.json()
    assert len(sarima_data["forecast"]) == 14

    # 3. Prophet Endpoint
    prophet_res = client.post(
        f"/api/forecast/prophet?dataset_id={dataset_id}&series_id=STORE_CA_ITEM_1&horizon=7"
    )
    assert prophet_res.status_code == 200
    prophet_data = prophet_res.json()
    assert len(prophet_data["forecast"]) == 7
    assert "weekly" in prophet_data["components"]

    # 4. Unified Forecast Endpoint
    req_body = {
        "dataset_id": dataset_id,
        "series_id": "STORE_CA_ITEM_1",
        "horizon": 28,
        "model": "arima",
        "arima_config": {"p": 1, "d": 1, "q": 1}
    }
    uni_res = client.post("/api/forecast/generate", json=req_body)
    assert uni_res.status_code == 200
    assert len(uni_res.json()["forecast"]) == 28


# 8. Unsupported Models Return Clear Error Messages
def test_unimplemented_future_models_response():
    req_body = {
        "dataset_id": "mock-id",
        "series_id": "S1",
        "horizon": 28,
        "model": "unsupported_xyz_model"
    }
    res = client.post("/api/forecast/generate", json=req_body)
    assert res.status_code == 400
    assert "Model is unavailable" in res.json()["detail"]
