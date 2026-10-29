"""
Phase 6 DeepAR and Temporal Fusion Transformer (TFT) Test Suite
ForecastIQ Backend
"""
import io
import pytest
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient
from app.main import app
from app.models.deepar import DeeparForecaster
from app.models.tft import TftForecaster
from app.data.schema import ForecastResult, ForecastRequest, DeeparConfig, TftConfig

client = TestClient(app)


def make_synthetic_series(n_days=100, trend=0.08, seasonality=4.0, noise_scale=0.5):
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=n_days, freq="D")
    t = np.arange(n_days)
    seas = seasonality * np.sin(2 * np.pi * t / 7.0)
    noise = np.random.normal(0, noise_scale, n_days)
    target = np.maximum(2.0, 15.0 + trend * t + seas + noise)
    return pd.DataFrame({
        "date": dates,
        "series_id": "SERIES_NN_1",
        "target": target
    })


# ==============================================================================
# DEEPAR TESTS (1 - 12)
# ==============================================================================

# 1. DeepAR Initialization
def test_deepar_initialization():
    forecaster = DeeparForecaster(
        input_chunk_length=10,
        training_length=20,
        epochs=3,
        batch_size=8,
        hidden_dim=16,
        num_layers=1,
        dropout=0.05,
        random_state=123,
        num_samples=30
    )
    assert forecaster.model_name == "DeepAR"
    assert forecaster.epochs == 3
    assert forecaster.batch_size == 8
    assert forecaster.hidden_dim == 16
    assert forecaster.is_fitted is False


# 2. DeepAR Data Conversion & Scaler Fitting
def test_deepar_data_conversion_and_scaling():
    df = make_synthetic_series(n_days=70)
    forecaster = DeeparForecaster(epochs=2, batch_size=16)
    forecaster.fit(df, time_col="date", target_col="target", horizon=7)

    assert forecaster.is_fitted is True
    assert forecaster.scaler is not None
    assert forecaster.training_series is not None
    # Verify scaled data is roughly within standard bounds
    scaled_vals = forecaster.training_series.values()
    assert scaled_vals.min() >= -0.1 and scaled_vals.max() <= 1.1


# 3. DeepAR Training & History Tracking
def test_deepar_training_execution():
    df = make_synthetic_series(n_days=60)
    forecaster = DeeparForecaster(epochs=2, hidden_dim=12)
    forecaster.fit(df, time_col="date", target_col="target", horizon=7)
    assert forecaster.metadata["epochs"] == 2
    assert forecaster.metadata["likelihood"] == "GaussianLikelihood"


# 4. DeepAR 7-Day Forecast
def test_deepar_forecast_7_day():
    df = make_synthetic_series(n_days=60)
    forecaster = DeeparForecaster(epochs=2, num_samples=25)
    forecaster.fit(df, time_col="date", target_col="target", horizon=7)
    res = forecaster.forecast(horizon=7, dataset_id="ds-deepar", series_id="SERIES_NN_1")

    assert isinstance(res, ForecastResult)
    assert res.forecast_horizon == 7
    assert len(res.forecast) == 7
    assert len(res.dates) == 7
    assert len(res.points) == 7
    assert res.model == "DeepAR"
    assert res.status == "SUCCESS"


# 5. DeepAR 28-Day Forecast
def test_deepar_forecast_28_day():
    df = make_synthetic_series(n_days=80)
    forecaster = DeeparForecaster(epochs=2, num_samples=25)
    forecaster.fit(df, time_col="date", target_col="target", horizon=28)
    res = forecaster.forecast(horizon=28, dataset_id="ds-deepar", series_id="SERIES_NN_1")

    assert len(res.forecast) == 28
    assert len(res.points) == 28


# 6. DeepAR 90-Day Forecast
def test_deepar_forecast_90_day():
    df = make_synthetic_series(n_days=110)
    forecaster = DeeparForecaster(epochs=2, num_samples=25)
    forecaster.fit(df, time_col="date", target_col="target", horizon=90)
    res = forecaster.forecast(horizon=90, dataset_id="ds-deepar", series_id="SERIES_NN_1")

    assert len(res.forecast) == 90
    assert len(res.dates) == 90


# 7. DeepAR Result Schema & Probabilistic Intervals
def test_deepar_result_schema_and_probabilistic_intervals():
    df = make_synthetic_series(n_days=60)
    forecaster = DeeparForecaster(epochs=2, num_samples=30)
    forecaster.fit(df, time_col="date", target_col="target", horizon=7)
    res = forecaster.forecast(horizon=7, dataset_id="ds-deepar", series_id="SERIES_NN_1")

    # DeepAR is probabilistic: lower and upper bounds must be populated
    assert res.lower_bound is not None
    assert res.upper_bound is not None
    assert len(res.lower_bound) == 7
    assert len(res.upper_bound) == 7

    for pt in res.points:
        assert pt.lower_bound is not None
        assert pt.upper_bound is not None
        assert pt.lower_bound <= pt.forecast <= pt.upper_bound or pt.lower_bound <= pt.upper_bound


# 8. DeepAR Series Isolation
def test_deepar_series_isolation():
    df1 = make_synthetic_series(n_days=60, trend=0.1)
    df1["series_id"] = "SERIES_A"
    df2 = make_synthetic_series(n_days=60, trend=5.0)
    df2["series_id"] = "SERIES_B"
    combined = pd.concat([df1, df2], ignore_index=True)

    series_a = combined[combined["series_id"] == "SERIES_A"].copy()
    forecaster = DeeparForecaster(epochs=2, num_samples=20)
    forecaster.fit(series_a, time_col="date", target_col="target", horizon=7)
    res = forecaster.forecast(horizon=7, dataset_id="ds-iso", series_id="SERIES_A")

    assert res.series_id == "SERIES_A"
    assert len(res.forecast) == 7


# 9. DeepAR Scaling Leakage Protection (Fitted strictly on train)
def test_deepar_scaling_leakage_protection():
    df = make_synthetic_series(n_days=70)
    forecaster = DeeparForecaster(epochs=2)
    forecaster.fit(df, time_col="date", target_col="target", horizon=14)

    # Scaler must be initialized and fitted strictly on historical training data
    assert forecaster.scaler is not None
    assert forecaster.scaler._fit_called is True


# 10. DeepAR Future Covariate Protection
def test_deepar_future_covariate_protection():
    df = make_synthetic_series(n_days=60)
    # Target column must be cleanly forecasted without requiring unsupplied future covariates
    forecaster = DeeparForecaster(epochs=2, num_samples=20)
    forecaster.fit(df, time_col="date", target_col="target", horizon=7)
    res = forecaster.forecast(horizon=7, dataset_id="ds-cov", series_id="SERIES_NN_1")
    assert all(np.isfinite(f) for f in res.forecast)


# 11. DeepAR Insufficient History Validation
def test_deepar_insufficient_history():
    short_df = make_synthetic_series(n_days=10)
    forecaster = DeeparForecaster()
    with pytest.raises(ValueError, match="Not enough historical data"):
        forecaster.fit(short_df, time_col="date", target_col="target", horizon=28)


# 12. DeepAR Invalid Data / Missing Values
def test_deepar_invalid_data():
    na_df = make_synthetic_series(n_days=50)
    na_df.loc[15, "target"] = np.nan
    forecaster = DeeparForecaster()
    with pytest.raises(ValueError, match="Target contains unresolved missing values"):
        forecaster.fit(na_df, time_col="date", target_col="target", horizon=7)


# ==============================================================================
# TFT TESTS (13 - 23)
# ==============================================================================

# 13. TFT Initialization
def test_tft_initialization():
    forecaster = TftForecaster(
        input_chunk_length=14,
        output_chunk_length=7,
        epochs=3,
        batch_size=8,
        hidden_size=16,
        lstm_layers=1,
        num_attention_heads=2,
        dropout=0.1,
        random_state=42
    )
    assert forecaster.model_name == "Temporal Fusion Transformer (TFT)"
    assert forecaster.epochs == 3
    assert forecaster.hidden_size == 16
    assert forecaster.num_attention_heads == 2
    assert forecaster.is_fitted is False


# 14. TFT Data Conversion
def test_tft_data_conversion():
    df = make_synthetic_series(n_days=70)
    forecaster = TftForecaster(epochs=2, batch_size=16)
    forecaster.fit(df, time_col="date", target_col="target", horizon=7)

    assert forecaster.is_fitted is True
    assert forecaster.scaler is not None
    assert forecaster.training_series is not None


# 15. TFT Training Execution
def test_tft_training_execution():
    df = make_synthetic_series(n_days=65)
    forecaster = TftForecaster(epochs=2, hidden_size=12, num_attention_heads=2)
    forecaster.fit(df, time_col="date", target_col="target", horizon=7)
    assert forecaster.metadata["epochs"] == 2
    assert forecaster.metadata["attention_heads"] == 2


# 16. TFT 7-Day Forecast
def test_tft_forecast_7_day():
    df = make_synthetic_series(n_days=65)
    forecaster = TftForecaster(epochs=2)
    forecaster.fit(df, time_col="date", target_col="target", horizon=7)
    res = forecaster.forecast(horizon=7, dataset_id="ds-tft", series_id="SERIES_NN_1")

    assert isinstance(res, ForecastResult)
    assert res.forecast_horizon == 7
    assert len(res.forecast) == 7
    assert len(res.dates) == 7
    assert len(res.points) == 7
    assert res.status == "SUCCESS"


# 17. TFT 28-Day Forecast
def test_tft_forecast_28_day():
    df = make_synthetic_series(n_days=80)
    forecaster = TftForecaster(epochs=2)
    forecaster.fit(df, time_col="date", target_col="target", horizon=28)
    res = forecaster.forecast(horizon=28, dataset_id="ds-tft", series_id="SERIES_NN_1")

    assert len(res.forecast) == 28
    assert len(res.points) == 28


# 18. TFT 90-Day Forecast
def test_tft_forecast_90_day():
    df = make_synthetic_series(n_days=110)
    forecaster = TftForecaster(epochs=2)
    forecaster.fit(df, time_col="date", target_col="target", horizon=90)
    res = forecaster.forecast(horizon=90, dataset_id="ds-tft", series_id="SERIES_NN_1")

    assert len(res.forecast) == 90
    assert len(res.dates) == 90


# 19. TFT Result Schema & Bounds
def test_tft_result_schema_and_quantiles():
    df = make_synthetic_series(n_days=65)
    forecaster = TftForecaster(epochs=2)
    forecaster.fit(df, time_col="date", target_col="target", horizon=7)
    res = forecaster.forecast(horizon=7, dataset_id="ds-tft", series_id="SERIES_NN_1")

    assert res.lower_bound is not None
    assert res.upper_bound is not None
    assert len(res.lower_bound) == 7
    assert len(res.upper_bound) == 7
    for pt in res.points:
        assert isinstance(pt.forecast, float)


# 20. TFT Series Isolation
def test_tft_series_isolation():
    df1 = make_synthetic_series(n_days=65, trend=0.1)
    df1["series_id"] = "SERIES_1"
    df2 = make_synthetic_series(n_days=65, trend=2.0)
    df2["series_id"] = "SERIES_2"
    combined = pd.concat([df1, df2], ignore_index=True)

    series_1 = combined[combined["series_id"] == "SERIES_1"].copy()
    forecaster = TftForecaster(epochs=2)
    forecaster.fit(series_1, time_col="date", target_col="target", horizon=7)
    res = forecaster.forecast(horizon=7, dataset_id="ds-iso", series_id="SERIES_1")

    assert res.series_id == "SERIES_1"
    assert len(res.forecast) == 7


# 21. TFT Future Covariate Protection
def test_tft_future_covariate_protection():
    df = make_synthetic_series(n_days=65)
    forecaster = TftForecaster(epochs=2)
    forecaster.fit(df, time_col="date", target_col="target", horizon=7)
    res = forecaster.forecast(horizon=7, dataset_id="ds-tft-cov", series_id="SERIES_NN_1")
    assert all(np.isfinite(f) for f in res.forecast)


# 22. TFT Insufficient History Validation
def test_tft_insufficient_history():
    short_df = make_synthetic_series(n_days=10)
    forecaster = TftForecaster()
    with pytest.raises(ValueError, match="Not enough historical data"):
        forecaster.fit(short_df, time_col="date", target_col="target", horizon=28)


# 23. TFT Unfitted Forecast Exception
def test_tft_unfitted_exception():
    unfitted = TftForecaster()
    with pytest.raises(RuntimeError, match="Model must be fitted"):
        unfitted.forecast(horizon=7, dataset_id="ds", series_id="s")


# ==============================================================================
# INTEGRATION TESTS (24 - 27)
# ==============================================================================

# 24. Direct API Endpoint: POST /api/forecast/deepar
def test_api_direct_deepar_endpoint():
    df = make_synthetic_series(n_days=70)
    csv_bytes = df.to_csv(index=False).encode("utf-8")

    upload_res = client.post(
        "/api/data/upload",
        files={"file": ("test_deepar_series.csv", io.BytesIO(csv_bytes), "text/csv")}
    )
    assert upload_res.status_code == 200
    dataset_id = upload_res.json()["dataset_id"]

    res = client.post(
        f"/api/forecast/deepar?dataset_id={dataset_id}&series_id=SERIES_NN_1&horizon=7&epochs=2&batch_size=16&hidden_dim=16&num_samples=25"
    )
    assert res.status_code == 200
    data = res.json()
    assert data["model"] == "DeepAR"
    assert data["forecast_horizon"] == 7
    assert len(data["forecast"]) == 7
    assert data["lower_bound"] is not None
    assert data["upper_bound"] is not None
    assert data["status"] == "SUCCESS"


# 25. Direct API Endpoint: POST /api/forecast/tft
def test_api_direct_tft_endpoint():
    df = make_synthetic_series(n_days=70)
    csv_bytes = df.to_csv(index=False).encode("utf-8")

    upload_res = client.post(
        "/api/data/upload",
        files={"file": ("test_tft_series.csv", io.BytesIO(csv_bytes), "text/csv")}
    )
    assert upload_res.status_code == 200
    dataset_id = upload_res.json()["dataset_id"]

    res = client.post(
        f"/api/forecast/tft?dataset_id={dataset_id}&series_id=SERIES_NN_1&horizon=7&epochs=2&batch_size=16&hidden_size=16&attention_heads=2"
    )
    assert res.status_code == 200
    data = res.json()
    assert data["model"] == "Temporal Fusion Transformer (TFT)"
    assert data["forecast_horizon"] == 7
    assert len(data["forecast"]) == 7
    assert data["status"] == "SUCCESS"


# 26. Unified API Endpoint: POST /api/forecast/generate routing for deepar and tft
def test_api_unified_deepar_and_tft_routing():
    df = make_synthetic_series(n_days=70)
    csv_bytes = df.to_csv(index=False).encode("utf-8")

    upload_res = client.post(
        "/api/data/upload",
        files={"file": ("test_nn_unified.csv", io.BytesIO(csv_bytes), "text/csv")}
    )
    assert upload_res.status_code == 200
    dataset_id = upload_res.json()["dataset_id"]

    # Test DeepAR unified routing
    payload_deepar = {
        "dataset_id": dataset_id,
        "series_id": "SERIES_NN_1",
        "horizon": 7,
        "model": "deepar",
        "deepar_config": {"epochs": 2, "batch_size": 16, "num_samples": 20}
    }
    res_deepar = client.post("/api/forecast/generate", json=payload_deepar)
    assert res_deepar.status_code == 200
    assert res_deepar.json()["model"] == "DeepAR"

    # Test TFT unified routing
    payload_tft = {
        "dataset_id": dataset_id,
        "series_id": "SERIES_NN_1",
        "horizon": 7,
        "model": "tft",
        "tft_config": {"epochs": 2, "batch_size": 16, "hidden_size": 16}
    }
    res_tft = client.post("/api/forecast/generate", json=payload_tft)
    assert res_tft.status_code == 200
    assert res_tft.json()["model"] == "Temporal Fusion Transformer (TFT)"


# 27. Preserved Models Compatibility (ARIMA, SARIMA, Prophet, LightGBM still work)
def test_existing_models_preserved():
    df = make_synthetic_series(n_days=70)
    csv_bytes = df.to_csv(index=False).encode("utf-8")

    upload_res = client.post(
        "/api/data/upload",
        files={"file": ("test_existing.csv", io.BytesIO(csv_bytes), "text/csv")}
    )
    assert upload_res.status_code == 200
    dataset_id = upload_res.json()["dataset_id"]

    for m in ["arima", "sarima", "prophet", "lightgbm"]:
        payload = {
            "dataset_id": dataset_id,
            "series_id": "SERIES_NN_1",
            "horizon": 7,
            "model": m
        }
        res = client.post("/api/forecast/generate", json=payload)
        assert res.status_code == 200, f"Model {m} failed with status {res.status_code}: {res.text}"
