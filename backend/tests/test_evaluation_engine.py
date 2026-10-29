"""
Phase 8 Backtesting, Evaluation, MAPE, RMSE and Model Comparison Test Suite
ForecastIQ Backend
"""
import os
import io
import pytest
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.evaluation.metrics import EvaluationMetrics
from app.evaluation.backtesting import BacktestingEngine, EVALUATION_CACHE
from app.forecasting.engine import UnifiedForecastEngine
from app.data.schema import ForecastRequest, BacktestRequest
from app.data.loader import save_dataset

client = TestClient(app)


def make_backtest_df(n_days=120, series_id="TEST_SERIES_1", start_date="2024-01-01"):
    np.random.seed(42)
    dates = pd.date_range(start_date, periods=n_days, freq="D")
    t = np.arange(n_days)
    # Clear weekly seasonality and gentle upward trend
    seasonality = 5.0 * np.sin(2 * np.pi * t / 7.0)
    trend = 0.05 * t
    target = np.maximum(2.0, 20.0 + trend + seasonality + np.random.normal(0, 0.5, n_days))
    return pd.DataFrame({
        "date": dates,
        "series_id": series_id,
        "target": target
    })


# 1. MAPE normal calculation
def test_mape_normal_calculation():
    actuals = [100.0, 200.0, 300.0, 400.0]
    preds = [110.0, 190.0, 330.0, 360.0]
    # |100-110|/100 = 0.10, |200-190|/200 = 0.05, |300-330|/300 = 0.10, |400-360|/400 = 0.10
    # Mean = (0.10 + 0.05 + 0.10 + 0.10) / 4 = 0.0875 -> 8.75%
    mape = EvaluationMetrics.calculate_mape(actuals, preds)
    assert mape["mape"] == 8.75


# 2. MAPE zero-actual policy exclusion
def test_mape_zero_actual_policy_exclusion():
    # Retail intermittent demand often has zero sales
    actuals = [100.0, 0.0, 200.0, 0.0]
    preds = [110.0, 5.0, 220.0, 0.0]
    metrics = EvaluationMetrics.evaluate_forecast(actuals, preds)
    # Zero actuals excluded from ratio:
    # Valid actuals: 100 (|100-110|/100 = 0.10), 200 (|200-220|/200 = 0.10) -> Mean = 10.0%
    assert metrics["mape"] == 10.0
    assert metrics["mape_valid_count"] == 2
    assert metrics["mape_zero_actual_count"] == 2
    assert metrics["sample_count"] == 4


# 3. MAPE all-zero actuals returns None
def test_mape_all_zero_actuals_returns_none():
    actuals = [0.0, 0.0, 0.0]
    preds = [5.0, 2.0, 1.0]
    mape = EvaluationMetrics.calculate_mape(actuals, preds)
    assert mape["mape"] is None

    metrics = EvaluationMetrics.evaluate_forecast(actuals, preds)
    assert metrics["mape"] is None
    assert metrics["mape_zero_actual_count"] == 3
    assert metrics["mape_valid_count"] == 0


# 4. RMSE normal calculation
def test_rmse_normal_calculation():
    actuals = [10.0, 20.0, 30.0]
    preds = [12.0, 20.0, 26.0]
    # Errors: 2, 0, -4. Squared: 4, 0, 16. Mean: 20/3 = 6.6667. Sqrt: ~2.58
    rmse = EvaluationMetrics.calculate_rmse(actuals, preds)
    assert rmse["rmse"] == round(float(np.sqrt(20.0 / 3.0)), 2)



# 5. Chronological rolling-origin folds without temporal leakage
def test_chronological_rolling_origin_folds_no_leakage():
    df = make_backtest_df(n_days=100)
    folds = BacktestingEngine.generate_rolling_origin_folds(
        series_df=df,
        time_col="date",
        horizon=7,
        n_folds=3,
        step_size=7,
        min_train_size=40,
    )
    assert len(folds) == 3

    for fold in folds:
        train_df = fold["train_df"]
        test_df = fold["test_df"]
        # Train and test must never overlap
        max_train_date = train_df["date"].max()
        min_test_date = test_df["date"].min()
        assert max_train_date < min_test_date, "Temporal leakage detected! Train date exceeds test date."
        assert len(test_df) == 7


# 6. Fold horizon and boundary alignment
def test_fold_horizon_and_boundary_alignment():
    df = make_backtest_df(n_days=110)
    folds = BacktestingEngine.generate_rolling_origin_folds(
        series_df=df,
        time_col="date",
        horizon=28,
        n_folds=2,
    )
    assert len(folds) >= 1
    for fold in folds:
        assert len(fold["test_df"]) == 28
        assert fold["forecast_start"] <= fold["forecast_end"]


# 7. Insufficient history for backtesting raises ValueError
def test_insufficient_history_for_backtesting():
    short_df = make_backtest_df(n_days=15)
    with pytest.raises(ValueError, match="Insufficient history"):
        BacktestingEngine.generate_rolling_origin_folds(
            series_df=short_df,
            time_col="date",
            horizon=28,
            min_train_size=50,
        )


# 8. ARIMA rolling-origin evaluation on series
def test_arima_backtest_evaluation():
    df = make_backtest_df(n_days=80)
    mapping = {"date": "date", "series_id": "series_id", "target": "target"}
    eval_res = BacktestingEngine.evaluate_model_on_series(
        dataset_id="TEST_DS_EVAL",
        series_id="TEST_SERIES_1",
        model_name="arima",
        horizon=7,
        series_df=df,
        mapping=mapping,
        n_folds=2,
    )
    assert eval_res["status"] == "SUCCESS"
    assert eval_res["model"] == "arima"
    assert eval_res["horizon"] == 7
    assert eval_res["mape"] is not None
    assert eval_res["rmse"] is not None
    assert len(eval_res["folds"]) == 2


# 9. SARIMA rolling-origin evaluation on series
def test_sarima_backtest_evaluation():
    df = make_backtest_df(n_days=80)
    mapping = {"date": "date", "series_id": "series_id", "target": "target"}
    eval_res = BacktestingEngine.evaluate_model_on_series(
        dataset_id="TEST_DS_EVAL",
        series_id="TEST_SERIES_1",
        model_name="sarima",
        horizon=7,
        series_df=df,
        mapping=mapping,
        n_folds=1,
    )
    assert eval_res["status"] == "SUCCESS"
    assert eval_res["model"] == "sarima"
    assert eval_res["mape"] is not None


# 10. Prophet rolling-origin evaluation on series
def test_prophet_backtest_evaluation():
    df = make_backtest_df(n_days=80)
    mapping = {"date": "date", "series_id": "series_id", "target": "target"}
    eval_res = BacktestingEngine.evaluate_model_on_series(
        dataset_id="TEST_DS_EVAL",
        series_id="TEST_SERIES_1",
        model_name="prophet",
        horizon=7,
        series_df=df,
        mapping=mapping,
        n_folds=1,
    )
    assert eval_res["status"] == "SUCCESS"
    assert eval_res["model"] == "prophet"
    assert eval_res["mape"] is not None


# 11. LightGBM rolling-origin evaluation on series
def test_lightgbm_backtest_evaluation():
    df = make_backtest_df(n_days=80)
    mapping = {"date": "date", "series_id": "series_id", "target": "target"}
    eval_res = BacktestingEngine.evaluate_model_on_series(
        dataset_id="TEST_DS_EVAL",
        series_id="TEST_SERIES_1",
        model_name="lightgbm",
        horizon=7,
        series_df=df,
        mapping=mapping,
        n_folds=1,
        model_kwargs={"n_estimators": 20},
    )
    assert eval_res["status"] == "SUCCESS"
    assert eval_res["model"] == "lightgbm"
    assert eval_res["mape"] is not None


# 12. DeepAR rolling-origin evaluation on series
def test_deepar_backtest_evaluation():
    df = make_backtest_df(n_days=80)
    mapping = {"date": "date", "series_id": "series_id", "target": "target"}
    eval_res = BacktestingEngine.evaluate_model_on_series(
        dataset_id="TEST_DS_EVAL",
        series_id="TEST_SERIES_1",
        model_name="deepar",
        horizon=7,
        series_df=df,
        mapping=mapping,
        n_folds=1,
        model_kwargs={"epochs": 1, "batch_size": 16, "num_samples": 10},
    )
    assert eval_res["status"] == "SUCCESS"
    assert eval_res["model"] == "deepar"
    assert eval_res["mape"] is not None


# 13. TFT rolling-origin evaluation on series
def test_tft_backtest_evaluation():
    df = make_backtest_df(n_days=80)
    mapping = {"date": "date", "series_id": "series_id", "target": "target"}
    eval_res = BacktestingEngine.evaluate_model_on_series(
        dataset_id="TEST_DS_EVAL",
        series_id="TEST_SERIES_1",
        model_name="tft",
        horizon=7,
        series_df=df,
        mapping=mapping,
        n_folds=1,
        model_kwargs={"epochs": 1, "batch_size": 16},
    )
    assert eval_res["status"] == "SUCCESS"
    assert eval_res["model"] == "tft"
    assert eval_res["mape"] is not None


# 14. Model ranking and tie handling
def test_model_ranking_and_tie_detection():
    # Synthetic evaluations with near-identical scores (within 0.2%)
    evaluations = [
        {
            "dataset_id": "DS_TIE",
            "series_id": "SERIES_1",
            "model": "lightgbm",
            "horizon": 7,
            "status": "SUCCESS",
            "mape": 9.15,
            "rmse": 5.2,
            "fold_count": 2,
            "sample_count": 14,
        },
        {
            "dataset_id": "DS_TIE",
            "series_id": "SERIES_1",
            "model": "tft",
            "horizon": 7,
            "status": "SUCCESS",
            "mape": 9.25,
            "rmse": 5.4,
            "fold_count": 2,
            "sample_count": 14,
        },
        {
            "dataset_id": "DS_TIE",
            "series_id": "SERIES_1",
            "model": "arima",
            "horizon": 7,
            "status": "SUCCESS",
            "mape": 14.5,
            "rmse": 8.0,
            "fold_count": 2,
            "sample_count": 14,
        }
    ]
    summary = BacktestingEngine._build_comparison_summary(
        dataset_id="DS_TIE",
        series_evaluations=evaluations,
        models=["lightgbm", "tft", "arima"],
        horizons=[7],
        total_duration_ms=100.0,
    )
    best_7d = summary["best_per_horizon"]["7D"]
    assert best_7d["best_model"] == "lightgbm"
    assert best_7d["is_tie"] is True  # 9.25 - 9.15 = 0.10 <= 0.2%
    assert "lightgbm" in best_7d["tied_models"]
    assert "tft" in best_7d["tied_models"]


# 15. Horizon degradation calculation across 7D vs 28D
def test_horizon_degradation_calculation():
    evaluations = [
        {"dataset_id": "DS_DEG", "series_id": "S1", "model": "arima", "horizon": 7, "status": "SUCCESS", "mape": 8.0, "rmse": 4.0, "fold_count": 1, "sample_count": 7},
        {"dataset_id": "DS_DEG", "series_id": "S1", "model": "arima", "horizon": 28, "status": "SUCCESS", "mape": 14.0, "rmse": 7.5, "fold_count": 1, "sample_count": 28},
    ]
    summary = BacktestingEngine._build_comparison_summary(
        dataset_id="DS_DEG",
        series_evaluations=evaluations,
        models=["arima"],
        horizons=[7, 28],
        total_duration_ms=50.0,
    )
    table_1 = summary["table_1_model_x_horizon_mape"]
    assert table_1["arima"]["7D"] == 8.0
    assert table_1["arima"]["28D"] == 14.0
    # Degradation from 7D to 28D is positive (error grows as horizon extends)
    assert table_1["arima"]["28D"] > table_1["arima"]["7D"]


# 16. Automatic model selection using empirical backtest metrics
def test_automatic_selection_with_backtest_results():
    ds_id = "DS_AUTO_EVAL_TEST"
    df = make_backtest_df(n_days=90, series_id="SERIES_AUTO")
    save_dataset(ds_id, df, "auto_test.csv")

    # Pre-cache an evaluation where LightGBM is proven best for 7D
    EVALUATION_CACHE[ds_id] = {
        "dataset_id": ds_id,
        "best_per_horizon": {
            "7D": {"best_model": "lightgbm", "mape": 7.5, "rmse": 3.2, "is_tie": False, "tied_models": []}
        },
        "best_model_overall": {"model": "lightgbm", "overall_mape": 7.5},
        "table_3_series_evaluations": [
            {"series_id": "SERIES_AUTO", "model": "lightgbm", "horizon": "7D", "mape": 7.5, "rmse": 3.2}
        ]
    }

    req = ForecastRequest(
        dataset_id=ds_id,
        series_id="SERIES_AUTO",
        horizon=7,
        model="automatic",
    )
    res = UnifiedForecastEngine.execute(req)
    assert "LightGBM" in res.model
    assert any("LightGBM" in str(n) for n in res.notes)


# 17. Automatic model mode before backtesting reports unbacktested status
def test_automatic_mode_prior_to_backtesting():
    ds_id = "DS_AUTO_UNBACKTESTED"
    df = make_backtest_df(n_days=90, series_id="SERIES_FRESH")
    save_dataset(ds_id, df, "fresh.csv")
    # Ensure cache is clear
    EVALUATION_CACHE.pop(ds_id, None)

    req = ForecastRequest(
        dataset_id=ds_id,
        series_id="SERIES_FRESH",
        horizon=7,
        model="automatic",
    )
    res = UnifiedForecastEngine.execute(req)
    # Automatic mode executes candidate models and indicates empirical backtesting is pending
    assert res.model is not None
    assert any("backtesting" in str(n).lower() for n in res.notes)


# 18. Real M5 sample backtesting smoke test
def test_real_m5_sample_backtesting_smoke_test():
    ds_id = "DS_M5_SMOKE"
    df = make_backtest_df(n_days=95, series_id="FOODS_3_090_CA_1")
    df["store_id"] = "CA_1"
    df["item_id"] = "FOODS_3_090"
    save_dataset(ds_id, df, "m5_sample.csv")

    suite = BacktestingEngine.run_backtest_suite(
        dataset_id=ds_id,
        series_ids=["FOODS_3_090_CA_1"],
        models=["arima", "lightgbm"],
        horizons=[7],
        n_folds=1,
    )
    assert suite["dataset_id"] == ds_id
    assert "arima" in suite["models_evaluated"]
    assert "lightgbm" in suite["models_evaluated"]
    assert "7D" in suite["horizons_evaluated"]
    assert suite["best_per_horizon"]["7D"] is not None
    assert suite["best_per_horizon"]["7D"]["best_model"] in ["arima", "lightgbm"]


# 19. Generic enterprise dataset backtesting smoke test
def test_generic_enterprise_dataset_backtesting_smoke_test():
    ds_id = "DS_GENERIC_SMOKE"
    dates = pd.date_range("2023-01-01", periods=90, freq="D")
    df = pd.DataFrame({
        "timestamp": dates,
        "sku_code": "SKU_LOGISTICS_99",
        "units": np.random.uniform(50, 150, 90),
    })
    save_dataset(ds_id, df, "logistics.csv")

    suite = BacktestingEngine.run_backtest_suite(
        dataset_id=ds_id,
        series_ids=["SKU_LOGISTICS_99"],
        models=["arima", "prophet"],
        horizons=[7],
        n_folds=1,
    )
    assert suite["dataset_id"] == ds_id
    assert suite["table_1_model_x_horizon_mape"]["arima"]["7D"] is not None
    assert suite["table_1_model_x_horizon_mape"]["prophet"]["7D"] is not None


# 20. Evaluation API endpoints integration
def test_evaluation_api_endpoints():
    ds_id = "DS_API_TEST"
    df = make_backtest_df(n_days=85, series_id="SERIES_API")
    save_dataset(ds_id, df, "api_eval.csv")

    # 1. Trigger backtesting
    backtest_payload = {
        "dataset_id": ds_id,
        "series_ids": ["SERIES_API"],
        "models": ["arima", "lightgbm"],
        "horizons": [7],
        "n_folds": 1
    }
    post_res = client.post("/api/evaluation/backtest", json=backtest_payload)
    assert post_res.status_code == 200, post_res.text
    data = post_res.json()
    assert data["dataset_id"] == ds_id
    assert "table_1_model_x_horizon_mape" in data
    assert "table_2_model_x_horizon_rmse" in data

    # 2. GET /api/evaluation/{id}
    get_res = client.get(f"/api/evaluation/{ds_id}")
    assert get_res.status_code == 200
    assert get_res.json()["dataset_id"] == ds_id

    # 3. GET /api/evaluation/{id}/comparison
    comp_res = client.get(f"/api/evaluation/{ds_id}/comparison")
    assert comp_res.status_code == 200
    assert "table_1_model_x_horizon_mape" in comp_res.json()

    # 4. GET /api/evaluation/{id}/series/{series_id}
    series_res = client.get(f"/api/evaluation/{ds_id}/series/SERIES_API")
    assert series_res.status_code == 200
    assert series_res.json()["series_id"] == "SERIES_API"

    # 5. GET /api/evaluation/{id}/best-model
    best_res = client.get(f"/api/evaluation/{ds_id}/best-model?series_id=SERIES_API&horizon=7")
    assert best_res.status_code == 200
    assert best_res.json()["best_model"] in ["arima", "lightgbm"]


# 21. 194-day dataset fold bounds and dates (no indices > 194, no 1773/1913 leakage)
def test_194_day_canonical_m5_fold_bounds_and_dates():
    # 194 observations matching m5_canonical_sample.csv (2015-10-14 to 2016-04-24)
    start_date = "2015-10-14"
    n_days = 194
    df = make_backtest_df(n_days=n_days, series_id="HOBBIES_1_001_CA_1", start_date=start_date)

    # 7-day horizon with 2 folds
    folds_7d = BacktestingEngine.generate_rolling_origin_folds(
        series_df=df,
        time_col="date",
        horizon=7,
        n_folds=2,
    )
    assert len(folds_7d) == 2
    for fold in folds_7d:
        train_len = len(fold["train_df"])
        test_len = len(fold["test_df"])
        # Total days in train + test must never exceed 194
        assert train_len + test_len <= 194
        assert test_len == 7
        # Assert dates are within 2015-10-14 and 2016-04-24
        assert fold["train_df"]["date"].min() >= pd.Timestamp("2015-10-14")
        assert fold["test_df"]["date"].max() <= pd.Timestamp("2016-04-24")

    # 28-day horizon with 2 folds
    folds_28d = BacktestingEngine.generate_rolling_origin_folds(
        series_df=df,
        time_col="date",
        horizon=28,
        n_folds=2,
    )
    assert len(folds_28d) == 2
    for fold in folds_28d:
        assert len(fold["test_df"]) == 28
        assert len(fold["train_df"]) + len(fold["test_df"]) <= 194

    # 90-day horizon on 194 days requires min_history = 180 + 90 = 270 days, so it must raise ValueError
    with pytest.raises(ValueError, match="Insufficient history"):
        BacktestingEngine.generate_rolling_origin_folds(
            series_df=df,
            time_col="date",
            horizon=90,
            n_folds=1,
            min_train_size=180,
        )


# 22. Graceful suite execution with unavailable 90D horizon on a too-short dataset
def test_suite_execution_skips_unavailable_horizon():
    # HorizonManager: 90D needs min_history_required=100, so total needed = 100+90=190 days.
    # Use 120 days, which can support 7D and 28D but not 90D.
    ds_id = "DS_120_DAYS_SUITE"
    df = make_backtest_df(n_days=120, series_id="HOBBIES_1_001_CA_1", start_date="2015-10-14")
    save_dataset(ds_id, df, "m5_short_sample.csv")

    # Request [7, 28, 90] horizons on a 120-day dataset
    suite = BacktestingEngine.run_backtest_suite(
        dataset_id=ds_id,
        series_ids=["HOBBIES_1_001_CA_1"],
        models=["arima"],
        horizons=[7, 28, 90],
        n_folds=2,
    )

    # 7D and 28D succeed (14+7=21 days, 35+28=63 days required; both fine on 120)
    assert "7D" in suite["horizons_evaluated"]
    assert "28D" in suite["horizons_evaluated"]
    # 90D requires 100+90=190 days, 120 < 190, so it must be skipped without crashing
    assert "90D" not in suite["horizons_evaluated"]
    assert suite["table_1_model_x_horizon_mape"]["arima"]["7D"] is not None
    assert suite["table_1_model_x_horizon_mape"]["arima"]["28D"] is not None
    assert suite["table_1_model_x_horizon_mape"]["arima"]["90D"] is None


# 23. Sample-weighted aggregation across folds and series
def test_sample_weighted_metric_aggregation():
    # If fold A has 10 valid targets with 10% MAPE, and fold B has 90 valid targets with 20% MAPE:
    # Unweighted average = 15.0%
    # Weighted average = (10*10 + 90*20) / 100 = 19.0%
    series_evals = [
        {
            "status": "SUCCESS",
            "series_id": "SERIES_A",
            "model": "test_model",
            "horizon": 7,
            "mape": 10.0,
            "rmse": 5.0,
            "fold_count": 1,
            "sample_count": 10,
            "mape_valid_count": 10,
            "fold_evaluations": [{"mape": 10.0, "rmse": 5.0, "mape_valid_count": 10, "test_count": 10}],
        },
        {
            "status": "SUCCESS",
            "series_id": "SERIES_B",
            "model": "test_model",
            "horizon": 7,
            "mape": 20.0,
            "rmse": 10.0,
            "fold_count": 1,
            "sample_count": 90,
            "mape_valid_count": 90,
            "fold_evaluations": [{"mape": 20.0, "rmse": 10.0, "mape_valid_count": 90, "test_count": 90}],
        },
    ]

    summary = BacktestingEngine._build_comparison_summary(
        series_evaluations=series_evals,
        models=["test_model"],
        horizons=[7],
        dataset_id="TEST_WEIGHTED",
        total_duration_ms=0.0,
    )

    agg_mape = summary["table_1_model_x_horizon_mape"]["test_model"]["7D"]
    assert agg_mape == 19.0, f"Expected 19.0% weighted MAPE, got {agg_mape}"

    # Weighted RMSE check:
    # MSE_A = 25.0 * 10 = 250, MSE_B = 100.0 * 90 = 9000 -> Total MSE = 9250 / 100 = 92.5 -> sqrt(92.5) ~= 9.62
    agg_rmse = summary["table_2_model_x_horizon_rmse"]["test_model"]["7D"]
    assert agg_rmse == round(float(np.sqrt(92.5)), 2), f"Expected pooled RMSE, got {agg_rmse}"


# 24. 365-day dataset genuine 90-day walk-forward backtest evaluation
def test_365_day_dataset_90d_walk_forward_backtesting():
    # 365 observations allows min_train=100 + 2*90 = 280 <= 365 days
    ds_id = "DS_365_DAYS_SUITE"
    df = make_backtest_df(n_days=365, series_id="RETAIL_SERIES_1", start_date="2023-01-01")
    save_dataset(ds_id, df, "01_valid_retail_multiseries.csv")

    suite = BacktestingEngine.run_backtest_suite(
        dataset_id=ds_id,
        series_ids=["RETAIL_SERIES_1"],
        models=["arima", "lightgbm"],
        horizons=[7, 28, 90],
        n_folds=2,
    )

    assert "7D" in suite["horizons_evaluated"]
    assert "28D" in suite["horizons_evaluated"]
    assert "90D" in suite["horizons_evaluated"]

    # Verify Table 1 and Table 2 contain genuine finite numerical values for 90D
    mape_90_arima = suite["table_1_model_x_horizon_mape"]["arima"]["90D"]
    rmse_90_arima = suite["table_2_model_x_horizon_rmse"]["arima"]["90D"]
    assert mape_90_arima is not None and isinstance(mape_90_arima, float) and mape_90_arima > 0
    assert rmse_90_arima is not None and isinstance(rmse_90_arima, float) and rmse_90_arima > 0

    # Best per horizon for 90D must be populated
    best_90 = suite["best_per_horizon"]["90D"]
    assert best_90 is not None
    assert best_90["best_model"] in ["arima", "lightgbm"]
    assert best_90["mape"] is not None and best_90["mape"] > 0


# 25. Single-series dataset backtest evaluation without series_id
def test_single_series_backtesting_suite():
    ds_id = "DS_SINGLE_SERIES_SUITE"
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    df = pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "target": np.linspace(20, 60, 100) + np.random.normal(0, 0.5, 100)
    })
    save_dataset(ds_id, df, "single_series.csv")

    suite = BacktestingEngine.run_backtest_suite(
        dataset_id=ds_id,
        models=["arima"],
        horizons=[7, 28],
        n_folds=2,
    )

    assert suite["total_series_evaluated"] == 1
    assert "7D" in suite["horizons_evaluated"]
    assert "28D" in suite["horizons_evaluated"]
    assert suite["table_1_model_x_horizon_mape"]["arima"]["7D"] is not None
    assert suite["table_1_model_x_horizon_mape"]["arima"]["28D"] is not None
    assert suite["table_3_series_evaluations"][0]["series_id"] == "default_series"


# 26. Walmart weekly store sales schema backtest evaluation (Store, Dept, Date, Weekly_Sales, IsHoliday)
def test_walmart_store_sales_schema_backtesting():
    from app.data.loader import detect_candidate_columns
    ds_id = "DS_WALMART_TEST_SUITE"
    dates = pd.date_range("2010-02-05", periods=120, freq="W-FRI")
    
    # Create two store-dept combinations
    df_part1 = pd.DataFrame({
        "Store": 1,
        "Dept": 1,
        "Date": dates.strftime("%Y-%m-%d"),
        "Weekly_Sales": np.linspace(20000, 30000, 120) + np.random.normal(0, 500, 120),
        "IsHoliday": [False] * 120
    })
    df_part2 = pd.DataFrame({
        "Store": 1,
        "Dept": 2,
        "Date": dates.strftime("%Y-%m-%d"),
        "Weekly_Sales": np.linspace(40000, 50000, 120) + np.random.normal(0, 800, 120),
        "IsHoliday": [False] * 120
    })
    full_df = pd.concat([df_part1, df_part2], ignore_index=True)

    mapping = detect_candidate_columns(list(full_df.columns))
    assert mapping["date"] == "Date"
    assert mapping["target"] == "Weekly_Sales"
    assert "Store" in mapping["candidate_entity_columns"]
    assert "Dept" in mapping["candidate_entity_columns"]

    save_dataset(ds_id, full_df, "walmart_train.csv", mapping=mapping)

    suite = BacktestingEngine.run_backtest_suite(
        dataset_id=ds_id,
        models=["arima", "lightgbm"],
        horizons=[7, 28],
        n_folds=2,
    )

    assert suite["total_series_evaluated"] >= 1
    assert "7D" in suite["horizons_evaluated"]
    assert "28D" in suite["horizons_evaluated"]
    assert suite["table_1_model_x_horizon_mape"]["arima"]["7D"] is not None
    assert suite["table_1_model_x_horizon_mape"]["lightgbm"]["7D"] is not None




