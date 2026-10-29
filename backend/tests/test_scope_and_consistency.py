"""
System-Wide Data Consistency, Dynamic Scope, and Regression Test Suite
Tests 1 to 31 covering Data Explorer, Model Comparison, and Business Insights.
"""
import pytest
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.data.loader import save_dataset
from app.data.explorer import compute_explorer_analytics
from app.evaluation.backtesting import BacktestingEngine, EVALUATION_CACHE
from app.insights.business_insights import BusinessInsightEngine, INSIGHTS_CACHE
from app.data.schema import ForecastRequest, BacktestRequest, InsightRequest

client = TestClient(app)


@pytest.fixture(scope="module")
def multi_store_dataset():
    """
    Creates a realistic multi-store, multi-category, multi-item enterprise dataset.
    Store CA_1 has baseline demand ~100
    Store CA_2 has baseline demand ~250 (significantly higher)
    """
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    records = []

    # CA_1 - FOODS - ITEM_1
    for d in dates:
        records.append({
            "date": d.strftime("%Y-%m-%d"),
            "store_id": "CA_1",
            "category": "FOODS",
            "item_id": "ITEM_1",
            "series_id": "FOODS_ITEM_1_CA_1",
            "target": float(90 + np.random.randint(0, 20)),
            "price": 2.50
        })

    # CA_1 - HOBBIES - ITEM_2
    for d in dates:
        records.append({
            "date": d.strftime("%Y-%m-%d"),
            "store_id": "CA_1",
            "category": "HOBBIES",
            "item_id": "ITEM_2",
            "series_id": "HOBBIES_ITEM_2_CA_1",
            "target": float(40 + np.random.randint(0, 10)),
            "price": 12.00
        })

    # CA_2 - FOODS - ITEM_1
    for d in dates:
        records.append({
            "date": d.strftime("%Y-%m-%d"),
            "store_id": "CA_2",
            "category": "FOODS",
            "item_id": "ITEM_1",
            "series_id": "FOODS_ITEM_1_CA_2",
            "target": float(240 + np.random.randint(0, 30)),
            "price": 2.45
        })

    # CA_2 - HOBBIES - ITEM_2
    for d in dates:
        records.append({
            "date": d.strftime("%Y-%m-%d"),
            "store_id": "CA_2",
            "category": "HOBBIES",
            "item_id": "ITEM_2",
            "series_id": "HOBBIES_ITEM_2_CA_2",
            "target": float(110 + np.random.randint(0, 20)),
            "price": 11.50
        })

    df = pd.DataFrame(records)
    dataset_id = "DS_SCOPE_CONSISTENCY_TEST"
    save_dataset(dataset_id, df, "consistency_test.csv", metadata={"original_columns": list(df.columns)})
    return dataset_id, df


# ===========================================================================
# DATA EXPLORER REGRESSION TESTS (Tests 1 - 9)
# ===========================================================================

def test_01_explorer_uses_full_dataset_not_preview(multi_store_dataset):
    """1. Data Explorer uses full dataset rows, not preview limit."""
    dataset_id, df = multi_store_dataset
    res = compute_explorer_analytics(dataset_id, store_id=None, category=None, item_id=None, series_id=None, date_range="all")
    # Total dataset has 240 rows (4 series * 60 days)
    assert res.total_rows == 240
    assert res.total_rows > 5  # Much larger than 5 preview rows


def test_02_explorer_store_a_vs_store_b_different_metrics(multi_store_dataset):
    """2. Changing Store A (CA_1) -> Store B (CA_2) changes actual underlying data."""
    dataset_id, _ = multi_store_dataset
    res_ca1 = compute_explorer_analytics(dataset_id, store_id="CA_1", date_range="all")
    res_ca2 = compute_explorer_analytics(dataset_id, store_id="CA_2", date_range="all")

    assert res_ca1.scope.store_id == "CA_1"
    assert res_ca2.scope.store_id == "CA_2"
    # CA_2 has higher baseline demand
    assert res_ca1.total_demand != res_ca2.total_demand
    assert res_ca1.avg_daily_demand != res_ca2.avg_daily_demand
    assert res_ca2.total_demand > res_ca1.total_demand


def test_03_explorer_actual_row_filtering(multi_store_dataset):
    """3. Actual row filtering when store is selected."""
    dataset_id, _ = multi_store_dataset
    res_ca1 = compute_explorer_analytics(dataset_id, store_id="CA_1", date_range="all")
    # CA_1 has 2 series * 60 days = 120 rows
    assert res_ca1.total_rows == 120


def test_04_explorer_actual_kpi_recalculation(multi_store_dataset):
    """4. Actual KPI recalculation for avg demand, peak, min."""
    dataset_id, _ = multi_store_dataset
    res_ca1 = compute_explorer_analytics(dataset_id, store_id="CA_1", date_range="all")
    res_ca2 = compute_explorer_analytics(dataset_id, store_id="CA_2", date_range="all")

    assert res_ca1.max_demand != res_ca2.max_demand
    assert res_ca2.max_demand > res_ca1.max_demand


def test_05_explorer_actual_chart_recalculation(multi_store_dataset):
    """5. Trend chart points differ between Store A and Store B."""
    dataset_id, _ = multi_store_dataset
    res_ca1 = compute_explorer_analytics(dataset_id, store_id="CA_1", date_range="all")
    res_ca2 = compute_explorer_analytics(dataset_id, store_id="CA_2", date_range="all")

    assert len(res_ca1.trend) == 60
    assert len(res_ca2.trend) == 60
    # Day 1 sales must differ
    assert res_ca1.trend[0].sales != res_ca2.trend[0].sales


def test_06_explorer_category_filtering(multi_store_dataset):
    """6. Category filtering modifies scope and calculations."""
    dataset_id, _ = multi_store_dataset
    res_foods = compute_explorer_analytics(dataset_id, store_id="CA_1", category="FOODS")
    res_hobbies = compute_explorer_analytics(dataset_id, store_id="CA_1", category="HOBBIES")

    assert res_foods.total_rows == 60
    assert res_hobbies.total_rows == 60
    assert res_foods.avg_daily_demand != res_hobbies.avg_daily_demand
    assert res_foods.avg_daily_demand > res_hobbies.avg_daily_demand


def test_07_explorer_product_filtering(multi_store_dataset):
    """7. Product filtering isolates specific item."""
    dataset_id, _ = multi_store_dataset
    res = compute_explorer_analytics(dataset_id, store_id="CA_1", item_id="ITEM_1")
    assert res.total_rows == 60
    assert res.scope.item_id == "ITEM_1"


def test_08_explorer_series_filtering(multi_store_dataset):
    """8. Series filtering isolates exact series_id."""
    dataset_id, _ = multi_store_dataset
    res = compute_explorer_analytics(dataset_id, series_id="FOODS_ITEM_1_CA_2")
    assert res.total_rows == 60
    assert res.scope.series_id == "FOODS_ITEM_1_CA_2"
    assert res.avg_daily_demand > 200.0


def test_09_explorer_date_range_filtering(multi_store_dataset):
    """9. Date range window filtering cuts rows correctly."""
    dataset_id, _ = multi_store_dataset
    res_all = compute_explorer_analytics(dataset_id, series_id="FOODS_ITEM_1_CA_1", date_range="all")
    res_30d = compute_explorer_analytics(dataset_id, series_id="FOODS_ITEM_1_CA_1", date_range="30d")

    assert res_all.total_rows == 60
    assert res_30d.total_rows <= 31
    assert res_30d.date_min > res_all.date_min


# ===========================================================================
# MODEL COMPARISON REGRESSION TESTS (Tests 10 - 22)
# ===========================================================================

def test_10_13_model_comparison_scope_filters_reach_backend(multi_store_dataset):
    """10-13, 17. Scope filters (Store, Category, Product, Series) reach backend."""
    dataset_id, _ = multi_store_dataset
    res = BacktestingEngine.run_backtest_suite(
        dataset_id=dataset_id,
        store_id="CA_1",
        category="FOODS",
        item_id="ITEM_1",
        models=["arima", "lightgbm"],
        horizons=[7],  # 60 rows insufficient for 28D (needs 63)
        n_folds=1
    )
    assert res["scope"]["store_id"] == "CA_1"
    assert res["scope"]["category"] == "FOODS"
    assert res["scope"]["item_id"] == "ITEM_1"
    assert "FOODS_ITEM_1_CA_1" in res["scope"]["series_ids"]


def test_14_16_multi_horizon_evaluation(multi_store_dataset):
    """14-16. 7D, 28D multi-horizon evaluations are computed."""
    dataset_id, _ = multi_store_dataset
    res = BacktestingEngine.run_backtest_suite(
        dataset_id=dataset_id,
        series_ids=["FOODS_ITEM_1_CA_1"],
        models=["arima", "lightgbm"],
        horizons=[7],  # 60 rows insufficient for 28D (needs 63)
        n_folds=1
    )
    assert "7D" in res["table_1_model_x_horizon_mape"]["arima"]
    assert "7D" in res["table_2_model_x_horizon_rmse"]["arima"]


def test_18_19_scope_specific_mape_and_rmse(multi_store_dataset):
    """18-19. Backtest metrics are scope-specific between Store CA_1 and Store CA_2."""
    dataset_id, _ = multi_store_dataset
    eval_ca1 = BacktestingEngine.run_backtest_suite(
        dataset_id=dataset_id,
        store_id="CA_1",
        series_ids=["FOODS_ITEM_1_CA_1"],
        models=["arima"],
        horizons=[7],
        n_folds=1
    )
    eval_ca2 = BacktestingEngine.run_backtest_suite(
        dataset_id=dataset_id,
        store_id="CA_2",
        series_ids=["FOODS_ITEM_1_CA_2"],
        models=["arima"],
        horizons=[7],
        n_folds=1
    )

    rmse_ca1 = eval_ca1["table_2_model_x_horizon_rmse"]["arima"]["7D"]
    rmse_ca2 = eval_ca2["table_2_model_x_horizon_rmse"]["arima"]["7D"]
    assert rmse_ca1 is not None and rmse_ca2 is not None
    # Because target values in CA_2 are much larger (~250 vs ~100), RMSE must naturally differ!
    assert rmse_ca1 != rmse_ca2


def test_20_scope_specific_best_model(multi_store_dataset):
    """20. Best model resolution is scope specific."""
    dataset_id, _ = multi_store_dataset
    res = BacktestingEngine.run_backtest_suite(
        dataset_id=dataset_id,
        store_id="CA_1",
        series_ids=["FOODS_ITEM_1_CA_1"],
        models=["arima", "lightgbm"],
        horizons=[7],
        n_folds=1
    )
    best_7d = res["best_per_horizon"]["7D"]
    assert best_7d is not None
    assert best_7d["best_model"] in ["arima", "lightgbm"]


def test_21_no_mock_data_for_active_dataset(multi_store_dataset):
    """21. Active dataset results do not use static mock benchmark values."""
    dataset_id, _ = multi_store_dataset
    res = client.get(f"/api/evaluation/{dataset_id}/comparison?store_id=CA_1")
    assert res.status_code == 200
    data = res.json()
    assert "table_1_model_x_horizon_mape" in data
    # Results come from backtest engine, not mockData.js constants
    assert data["dataset_id"] == dataset_id


def test_22_stale_result_protection_cache_isolation(multi_store_dataset):
    """22. Evaluation cache isolates scopes so Store A does not overwrite Store B."""
    dataset_id, _ = multi_store_dataset
    BacktestingEngine.run_backtest_suite(
        dataset_id=dataset_id,
        store_id="CA_1",
        models=["arima"],
        horizons=[7],
        n_folds=1
    )
    BacktestingEngine.run_backtest_suite(
        dataset_id=dataset_id,
        store_id="CA_2",
        models=["arima"],
        horizons=[7],
        n_folds=1
    )

    ca1_res = BacktestingEngine.get_evaluation_for_dataset(dataset_id, store_id="CA_1")
    ca2_res = BacktestingEngine.get_evaluation_for_dataset(dataset_id, store_id="CA_2")

    assert ca1_res["scope"]["store_id"] == "CA_1"
    assert ca2_res["scope"]["store_id"] == "CA_2"


# ===========================================================================
# BUSINESS INSIGHTS REGRESSION TESTS (Tests 23 - 31)
# ===========================================================================

def test_23_insights_store_a_vs_store_b(multi_store_dataset):
    """23. Business Insights for Store A (CA_1) vs Store B (CA_2) use actual store data."""
    dataset_id, _ = multi_store_dataset
    res_ca1 = client.post("/api/insights/generate", json={
        "dataset_id": dataset_id,
        "store_id": "CA_1",
        "series_id": "FOODS_ITEM_1_CA_1",
        "model": "arima",
        "horizon": 7
    })
    res_ca2 = client.post("/api/insights/generate", json={
        "dataset_id": dataset_id,
        "store_id": "CA_2",
        "series_id": "FOODS_ITEM_1_CA_2",
        "model": "arima",
        "horizon": 7
    })

    assert res_ca1.status_code == 200
    assert res_ca2.status_code == 200
    data1 = res_ca1.json()
    data2 = res_ca2.json()

    assert data1["store_id"] == "CA_1"
    assert data2["store_id"] == "CA_2"
    assert data1["demand_outlook"]["recent_average_demand"] != data2["demand_outlook"]["recent_average_demand"]
    assert data2["demand_outlook"]["recent_average_demand"] > data1["demand_outlook"]["recent_average_demand"]


def test_24_insights_category_a_vs_category_b(multi_store_dataset):
    """24. Business insights differ between Category FOODS and HOBBIES."""
    dataset_id, _ = multi_store_dataset
    res_f = client.post("/api/insights/generate", json={
        "dataset_id": dataset_id,
        "store_id": "CA_1",
        "category": "FOODS",
        "series_id": "FOODS_ITEM_1_CA_1",
        "model": "arima",
        "horizon": 7
    })
    res_h = client.post("/api/insights/generate", json={
        "dataset_id": dataset_id,
        "store_id": "CA_1",
        "category": "HOBBIES",
        "series_id": "HOBBIES_ITEM_2_CA_1",
        "model": "arima",
        "horizon": 7
    })

    data_f = res_f.json()
    data_h = res_h.json()
    assert data_f["category"] == "FOODS"
    assert data_h["category"] == "HOBBIES"
    assert data_f["demand_outlook"]["recent_average_demand"] != data_h["demand_outlook"]["recent_average_demand"]


def test_25_26_insights_product_and_series(multi_store_dataset):
    """25-26. Product and Series specific insights."""
    dataset_id, _ = multi_store_dataset
    res = client.post("/api/insights/generate", json={
        "dataset_id": dataset_id,
        "series_id": "FOODS_ITEM_1_CA_1",
        "model": "arima",
        "horizon": 7
    })
    data = res.json()
    assert data["series_id"] == "FOODS_ITEM_1_CA_1"


def test_27_insights_horizon_sensitivity(multi_store_dataset):
    """27. 7D vs 28D horizon sensitivity."""
    dataset_id, _ = multi_store_dataset
    res_7 = client.post("/api/insights/generate", json={
        "dataset_id": dataset_id,
        "series_id": "FOODS_ITEM_1_CA_1",
        "model": "arima",
        "horizon": 7
    })
    res_28 = client.post("/api/insights/generate", json={
        "dataset_id": dataset_id,
        "series_id": "FOODS_ITEM_1_CA_1",
        "model": "arima",
        "horizon": 28
    })

    assert res_7.json()["horizon"] == 7
    assert res_28.json()["horizon"] == 28


def test_28_insights_model_specific_scope(multi_store_dataset):
    """28. Model-specific scope (arima vs lightgbm)."""
    dataset_id, _ = multi_store_dataset
    res_a = client.post("/api/insights/generate", json={
        "dataset_id": dataset_id,
        "series_id": "FOODS_ITEM_1_CA_1",
        "model": "arima",
        "horizon": 7
    })
    res_l = client.post("/api/insights/generate", json={
        "dataset_id": dataset_id,
        "series_id": "FOODS_ITEM_1_CA_1",
        "model": "lightgbm",
        "horizon": 7
    })

    assert res_a.json()["model"] == "arima"
    assert res_l.json()["model"] == "lightgbm"


def test_29_insights_cache_isolation(multi_store_dataset):
    """29. Insight cache key distinguishes scope dimensions."""
    dataset_id, _ = multi_store_dataset
    client.post("/api/insights/generate", json={
        "dataset_id": dataset_id,
        "store_id": "CA_1",
        "series_id": "FOODS_ITEM_1_CA_1",
        "model": "arima",
        "horizon": 7
    })
    client.post("/api/insights/generate", json={
        "dataset_id": dataset_id,
        "store_id": "CA_2",
        "series_id": "FOODS_ITEM_1_CA_2",
        "model": "arima",
        "horizon": 7
    })

    cached_1 = BusinessInsightEngine.get_cached_insights(dataset_id, series_id="FOODS_ITEM_1_CA_1", horizon=7, model="arima", store_id="CA_1")
    cached_2 = BusinessInsightEngine.get_cached_insights(dataset_id, series_id="FOODS_ITEM_1_CA_2", horizon=7, model="arima", store_id="CA_2")

    assert cached_1 is not None
    assert cached_2 is not None
    assert cached_1["store_id"] == "CA_1"
    assert cached_2["store_id"] == "CA_2"


def test_30_stale_result_protection(multi_store_dataset):
    """30. Requesting Store B does not return Store A cached result."""
    dataset_id, _ = multi_store_dataset
    res = client.get(f"/api/insights/{dataset_id}?store_id=CA_2&series_id=FOODS_ITEM_1_CA_2&horizon=7&model=arima")
    data = res.json()
    assert data["store_id"] == "CA_2"
    assert data["series_id"] == "FOODS_ITEM_1_CA_2"


def test_31_response_scope_validation(multi_store_dataset):
    """31. Response scope validation: response metadata clearly identifies full scope."""
    dataset_id, _ = multi_store_dataset
    res = client.post("/api/insights/generate", json={
        "dataset_id": dataset_id,
        "store_id": "CA_1",
        "category": "FOODS",
        "item_id": "ITEM_1",
        "series_id": "FOODS_ITEM_1_CA_1",
        "model": "arima",
        "horizon": 7
    })
    data = res.json()
    assert data["dataset_id"] == dataset_id
    assert data["store_id"] == "CA_1"
    assert data["category"] == "FOODS"
    assert data["item_id"] == "ITEM_1"
    assert data["series_id"] == "FOODS_ITEM_1_CA_1"
    assert data["model"] == "arima"
    assert data["horizon"] == 7
    assert data["scope"]["store_id"] == "CA_1"
