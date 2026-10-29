"""
Phase 7 Unified Multi-Horizon Forecasting Engine Test Suite
ForecastIQ Backend
"""
import io
import pytest
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient
from app.main import app
from app.forecasting.engine import UnifiedForecastEngine, ModelRegistry
from app.forecasting.horizon import HorizonManager
from app.data.schema import ForecastResult, ForecastRequest, ArimaConfig
from app.data.adapters.m5_adapter import M5Adapter

client = TestClient(app)


def make_synthetic_series(n_days=100, trend=0.1, seasonality=5.0):
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=n_days, freq="D")
    t = np.arange(n_days)
    seas = seasonality * np.sin(2 * np.pi * t / 7.0)
    target = np.maximum(5.0, 25.0 + trend * t + seas + np.random.normal(0, 0.5, n_days))
    return pd.DataFrame({
        "date": dates,
        "series_id": "SERIES_UNIFIED_1",
        "target": target
    })


# 1. Model Registry Listing and Factory
def test_model_registry_factory():
    models = ModelRegistry.list_models()
    assert "arima" in models
    assert "sarima" in models
    assert "prophet" in models
    assert "lightgbm" in models
    assert "deepar" in models
    assert "tft" in models

    arima_instance = ModelRegistry.create("arima", p=2, d=1, q=1)
    assert arima_instance.model_name == "ARIMA"

    lgbm_instance = ModelRegistry.create("lightgbm", n_estimators=50)
    assert lgbm_instance.model_name == "LightGBM"

    with pytest.raises(ValueError, match="Model is unavailable"):
        ModelRegistry.create("non_existent_model")


# 2. Horizon Manager Validation
def test_horizon_manager_validation():
    assert HorizonManager.validate_horizon(7) == 7
    assert HorizonManager.validate_horizon(28) == 28
    assert HorizonManager.validate_horizon(90) == 90

    with pytest.raises(ValueError, match="Invalid forecast horizon"):
        HorizonManager.validate_horizon(15)

    with pytest.raises(ValueError, match="Not enough historical data"):
        HorizonManager.validate_history_sufficiency(horizon=90, observation_count=50, model_name="ARIMA")


# 3. Unified Engine ARIMA Routing
def test_unified_engine_arima_routing():
    df = make_synthetic_series(n_days=70)
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    upload_res = client.post("/api/data/upload", files={"file": ("synth_arima.csv", io.BytesIO(csv_bytes), "text/csv")})
    dataset_id = upload_res.json()["dataset_id"]

    req = ForecastRequest(
        dataset_id=dataset_id,
        series_id="SERIES_UNIFIED_1",
        horizon=7,
        model="arima",
        arima_config=ArimaConfig(p=1, d=1, q=1)
    )
    res = UnifiedForecastEngine.execute(req)
    assert isinstance(res, ForecastResult)
    assert "ARIMA" in res.model
    assert res.forecast_horizon == 7
    assert len(res.forecast) == 7


# 4. Unified Engine SARIMA Routing
def test_unified_engine_sarima_routing():
    df = make_synthetic_series(n_days=70)
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    upload_res = client.post("/api/data/upload", files={"file": ("synth_sarima.csv", io.BytesIO(csv_bytes), "text/csv")})
    dataset_id = upload_res.json()["dataset_id"]

    req = ForecastRequest(
        dataset_id=dataset_id,
        series_id="SERIES_UNIFIED_1",
        horizon=7,
        model="sarima"
    )
    res = UnifiedForecastEngine.execute(req)
    assert "SARIMA" in res.model
    assert len(res.forecast) == 7


# 5. Unified Engine Prophet Routing
def test_unified_engine_prophet_routing():
    df = make_synthetic_series(n_days=70)
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    upload_res = client.post("/api/data/upload", files={"file": ("synth_prophet.csv", io.BytesIO(csv_bytes), "text/csv")})
    dataset_id = upload_res.json()["dataset_id"]

    req = ForecastRequest(
        dataset_id=dataset_id,
        series_id="SERIES_UNIFIED_1",
        horizon=7,
        model="prophet"
    )
    res = UnifiedForecastEngine.execute(req)
    assert res.model == "Prophet"
    assert len(res.forecast) == 7
    assert res.lower_bound is not None


# 6. Unified Engine LightGBM Routing & Null Bounds Verification
def test_unified_engine_lightgbm_routing_null_bounds():
    df = make_synthetic_series(n_days=80)
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    upload_res = client.post("/api/data/upload", files={"file": ("synth_lgbm.csv", io.BytesIO(csv_bytes), "text/csv")})
    dataset_id = upload_res.json()["dataset_id"]

    req = ForecastRequest(
        dataset_id=dataset_id,
        series_id="SERIES_UNIFIED_1",
        horizon=28,
        model="lightgbm"
    )
    res = UnifiedForecastEngine.execute(req)
    assert res.model == "LightGBM"
    assert len(res.forecast) == 28
    # Uncertainty rule: no fake intervals for LightGBM
    assert res.lower_bound is None
    assert res.upper_bound is None


# 7. Unified Engine DeepAR Routing
def test_unified_engine_deepar_routing():
    df = make_synthetic_series(n_days=70)
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    upload_res = client.post("/api/data/upload", files={"file": ("synth_deepar.csv", io.BytesIO(csv_bytes), "text/csv")})
    dataset_id = upload_res.json()["dataset_id"]

    req = ForecastRequest(
        dataset_id=dataset_id,
        series_id="SERIES_UNIFIED_1",
        horizon=7,
        model="deepar",
        deepar_config={"epochs": 2, "batch_size": 16, "num_samples": 20}
    )
    res = UnifiedForecastEngine.execute(req)
    assert res.model == "DeepAR"
    assert len(res.forecast) == 7
    assert res.lower_bound is not None


# 8. Unified Engine TFT Routing
def test_unified_engine_tft_routing():
    df = make_synthetic_series(n_days=70)
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    upload_res = client.post("/api/data/upload", files={"file": ("synth_tft.csv", io.BytesIO(csv_bytes), "text/csv")})
    dataset_id = upload_res.json()["dataset_id"]

    req = ForecastRequest(
        dataset_id=dataset_id,
        series_id="SERIES_UNIFIED_1",
        horizon=7,
        model="tft",
        tft_config={"epochs": 2, "batch_size": 16, "hidden_size": 16}
    )
    res = UnifiedForecastEngine.execute(req)
    assert res.model == "Temporal Fusion Transformer (TFT)"
    assert len(res.forecast) == 7


# 9. Unified Engine Automatic Mode Orchestration
def test_unified_engine_automatic_mode():
    df = make_synthetic_series(n_days=70)
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    upload_res = client.post("/api/data/upload", files={"file": ("synth_auto.csv", io.BytesIO(csv_bytes), "text/csv")})
    dataset_id = upload_res.json()["dataset_id"]

    req = ForecastRequest(
        dataset_id=dataset_id,
        series_id="SERIES_UNIFIED_1",
        horizon=7,
        model="automatic",
        deepar_config={"epochs": 1, "num_samples": 15},
        tft_config={"epochs": 1}
    )
    res = UnifiedForecastEngine.execute(req)
    assert "Automatic" in res.model
    assert res.forecast_horizon == 7
    assert len(res.forecast) == 7
    assert "model_forecasts" in res.components
    assert "arima" in res.components["model_forecasts"]
    assert "prophet" in res.components["model_forecasts"]


# 10. Invalid Model Error Handling
def test_unified_engine_invalid_model():
    df = make_synthetic_series(n_days=50)
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    upload_res = client.post("/api/data/upload", files={"file": ("synth_err.csv", io.BytesIO(csv_bytes), "text/csv")})
    dataset_id = upload_res.json()["dataset_id"]

    req = ForecastRequest(
        dataset_id=dataset_id,
        series_id="SERIES_UNIFIED_1",
        horizon=7,
        model="xgboost_not_supported"
    )
    with pytest.raises(ValueError, match="Model is unavailable"):
        UnifiedForecastEngine.execute(req)


# 11. Invalid Horizon Error Handling
def test_unified_engine_invalid_horizon():
    df = make_synthetic_series(n_days=50)
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    upload_res = client.post("/api/data/upload", files={"file": ("synth_err2.csv", io.BytesIO(csv_bytes), "text/csv")})
    dataset_id = upload_res.json()["dataset_id"]

    req = ForecastRequest(
        dataset_id=dataset_id,
        series_id="SERIES_UNIFIED_1",
        horizon=14,  # Not 7, 28, or 90
        model="arima"
    )
    with pytest.raises(ValueError, match="Invalid forecast horizon"):
        UnifiedForecastEngine.execute(req)


# 12. Nonexistent Dataset and Series
def test_unified_engine_nonexistent_dataset_and_series():
    req_bad_ds = ForecastRequest(
        dataset_id="unknown_ds_123",
        series_id="S1",
        horizon=7,
        model="arima"
    )
    with pytest.raises(ValueError, match="not found"):
        UnifiedForecastEngine.execute(req_bad_ds)

    df = make_synthetic_series(n_days=50)
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    upload_res = client.post("/api/data/upload", files={"file": ("synth_err3.csv", io.BytesIO(csv_bytes), "text/csv")})
    dataset_id = upload_res.json()["dataset_id"]

    req_bad_series = ForecastRequest(
        dataset_id=dataset_id,
        series_id="NON_EXISTENT_SERIES",
        horizon=7,
        model="arima"
    )
    with pytest.raises(ValueError, match="not found"):
        UnifiedForecastEngine.execute(req_bad_series)


# 13. Single-Series Isolation
def test_unified_engine_single_series_isolation():
    df1 = make_synthetic_series(n_days=60, trend=0.1)
    df1["series_id"] = "STORE_CA_1"
    df2 = make_synthetic_series(n_days=60, trend=5.0)
    df2["series_id"] = "STORE_TX_1"
    multi_df = pd.concat([df1, df2], ignore_index=True)

    csv_bytes = multi_df.to_csv(index=False).encode("utf-8")
    upload_res = client.post("/api/data/upload", files={"file": ("multi_series.csv", io.BytesIO(csv_bytes), "text/csv")})
    dataset_id = upload_res.json()["dataset_id"]

    req = ForecastRequest(
        dataset_id=dataset_id,
        series_id="STORE_CA_1",
        horizon=7,
        model="arima"
    )
    res = UnifiedForecastEngine.execute(req)
    assert res.series_id == "STORE_CA_1"
    assert len(res.forecast) == 7


# 14. Generic Non-M5 Dataset Smoke Test
def test_generic_enterprise_dataset_smoke_test():
    # Enterprise warehouse dataset with non-M5 columns
    n_days = 60
    dates = pd.date_range("2024-03-01", periods=n_days, freq="D")
    gen_df = pd.DataFrame({
        "date": dates,
        "series_id": "WH_EAST_SKU_491",
        "target": np.random.uniform(50, 150, n_days),
        "warehouse_zone": ["Zone_A"] * n_days,
        "ambient_temp": np.random.uniform(15, 25, n_days),
        "lead_time_days": [2] * n_days,
    })

    csv_bytes = gen_df.to_csv(index=False).encode("utf-8")
    upload_res = client.post("/api/data/upload", files={"file": ("generic_warehouse.csv", io.BytesIO(csv_bytes), "text/csv")})
    assert upload_res.status_code == 200
    dataset_id = upload_res.json()["dataset_id"]

    # Verify LightGBM and Prophet on generic dataset
    req_lgbm = ForecastRequest(
        dataset_id=dataset_id,
        series_id="WH_EAST_SKU_491",
        horizon=7,
        model="lightgbm"
    )
    res_lgbm = UnifiedForecastEngine.execute(req_lgbm)
    assert res_lgbm.model == "LightGBM"
    assert len(res_lgbm.forecast) == 7

    req_prophet = ForecastRequest(
        dataset_id=dataset_id,
        series_id="WH_EAST_SKU_491",
        horizon=7,
        model="prophet"
    )
    res_prophet = UnifiedForecastEngine.execute(req_prophet)
    assert res_prophet.model == "Prophet"
    assert len(res_prophet.forecast) == 7


# 15. Real M5 Dataset Sample Smoke Test
def test_real_m5_sample_smoke_test():
    # Convert real local M5 sample using M5Adapter
    conv_res = client.post("/api/data/m5/convert?max_series=2&max_days=60")
    if conv_res.status_code == 404:
        pytest.skip("M5 dataset files not found on server.")
    assert conv_res.status_code == 200
    dataset_id = conv_res.json()["dataset_id"]

    # Retrieve profile to find an M5 series ID
    prof_res = client.get(f"/api/data/{dataset_id}/preview")
    assert prof_res.status_code == 200
    m5_series_id = prof_res.json()["rows"][0]["series_id"]

    # Smoke Test 1: M5 + ARIMA + 7D
    req_arima = ForecastRequest(
        dataset_id=dataset_id,
        series_id=m5_series_id,
        horizon=7,
        model="arima"
    )
    res_arima = UnifiedForecastEngine.execute(req_arima)
    assert "ARIMA" in res_arima.model
    assert len(res_arima.forecast) == 7

    # Smoke Test 2: M5 + Prophet + 7D
    req_prophet = ForecastRequest(
        dataset_id=dataset_id,
        series_id=m5_series_id,
        horizon=7,
        model="prophet"
    )
    res_prophet = UnifiedForecastEngine.execute(req_prophet)
    assert res_prophet.model == "Prophet"
    assert len(res_prophet.forecast) == 7

    # Smoke Test 3: M5 + LightGBM + 7D
    req_lgbm = ForecastRequest(
        dataset_id=dataset_id,
        series_id=m5_series_id,
        horizon=7,
        model="lightgbm"
    )
    res_lgbm = UnifiedForecastEngine.execute(req_lgbm)
    assert res_lgbm.model == "LightGBM"
    assert len(res_lgbm.forecast) == 7
    assert res_lgbm.lower_bound is None


# 16. API Integration: POST /api/forecast/generate via Unified Engine
def test_api_unified_generate_endpoint_integration():
    df = make_synthetic_series(n_days=70)
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    upload_res = client.post("/api/data/upload", files={"file": ("synth_api.csv", io.BytesIO(csv_bytes), "text/csv")})
    dataset_id = upload_res.json()["dataset_id"]

    payload = {
        "dataset_id": dataset_id,
        "series_id": "SERIES_UNIFIED_1",
        "horizon": 28,
        "model": "arima"
    }
    res = client.post("/api/forecast/generate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "ARIMA" in data["model"]
    assert data["forecast_horizon"] == 28
    assert len(data["forecast"]) == 28
    assert len(data["points"]) == 28


# 17. Single series forecasting when series_id was omitted at upload
def test_forecast_single_series_omitted_series_id():
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    df = pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "target": np.linspace(10, 50, 60)
    })
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    upload_res = client.post("/api/data/upload", files={"file": ("single_series_api.csv", io.BytesIO(csv_bytes), "text/csv")})
    dataset_id = upload_res.json()["dataset_id"]

    # Generate forecast without specifying series_id or with default_series
    payload = {
        "dataset_id": dataset_id,
        "horizon": 7,
        "model": "arima"
    }
    res = client.post("/api/forecast/generate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["series_id"] == "default_series"
    assert len(data["forecast"]) == 7
