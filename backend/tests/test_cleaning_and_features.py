"""
Comprehensive Tests for Phase 3: Cleaning, Series Quality, Splits, Feature Engineering & Model Prep
ForecastIQ Backend
"""
import io
import pytest
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient
from app.main import app
from app.data.schema import (
    ColumnClassification,
    PipelineStatus,
)
from app.data.loader import load_csv_from_bytes, detect_candidate_columns
from app.data.cleaner import (
    clean_canonical_dataset,
    analyze_series_quality,
    compute_chronological_splits,
)
from app.features.analyzer import analyze_features
from app.features.engineer import (
    engineer_time_series_features,
    prepare_arima_dataset,
    prepare_prophet_dataset,
    prepare_lightgbm_dataset,
    prepare_darts_dataset,
)

client = TestClient(app)


# 1. Exact Duplicate Rows Detection and Removal
def test_exact_duplicates_cleaning():
    df = pd.DataFrame({
        "date": ["2024-01-01", "2024-01-01", "2024-01-02"],
        "series_id": ["S1", "S1", "S1"],
        "target": [10.0, 10.0, 15.0],
    })
    mapping = {"date": "date", "series_id": "series_id", "target": "target"}
    cleaned_df, report = clean_canonical_dataset("test-exact-dup", df, mapping)

    assert report.exact_duplicates_removed == 1
    assert len(cleaned_df) == 2
    assert report.cleaned_rows == 2


# 2. Conflicting (series_id, date) with Additive SUM Resolution
def test_conflicting_additive_sum_resolution():
    df = pd.DataFrame({
        "date": ["2024-01-01", "2024-01-01", "2024-01-02"],
        "series_id": ["STORE_1", "STORE_1", "STORE_1"],
        "target": [20.0, 30.0, 50.0],
        "promotion": [False, True, False],
        "price": [10.0, 12.0, 10.0],
    })
    mapping = {"date": "date", "series_id": "series_id", "target": "target"}
    cleaned_df, report = clean_canonical_dataset(
        "test-conflict-sum",
        df,
        mapping,
        additive_aggregation=True,
        target_type="additive"
    )

    assert report.conflicts_detected == 2
    assert report.conflicts_resolved == 1
    assert report.unresolved_conflicts == 0
    assert len(cleaned_df) == 2
    
    # 20.0 + 30.0 = 50.0
    day1_row = cleaned_df[cleaned_df["date"] == pd.Timestamp("2024-01-01")].iloc[0]
    assert day1_row["target"] == 50.0
    # Boolean promotion should be True (any True)
    assert day1_row["promotion"] == True


# 3. Conflicting (series_id, date) with Non-Additive Flagging
def test_conflicting_non_additive_flag():
    df = pd.DataFrame({
        "date": ["2024-01-01", "2024-01-01"],
        "series_id": ["SERIES_RATE", "SERIES_RATE"],
        "target": [0.05, 0.08],
    })
    mapping = {"date": "date", "series_id": "series_id", "target": "target"}
    cleaned_df, report = clean_canonical_dataset(
        "test-non-additive",
        df,
        mapping,
        additive_aggregation=False,
        target_type="non-additive"
    )

    assert report.unresolved_conflicts == 2
    assert report.aggregation_rule == "FLAG_FOR_REVIEW"
    assert report.pipeline_status == PipelineStatus.NEEDS_ATTENTION


# 4. Zero Target Preservation & Missing Target Audit
def test_zero_target_preservation_and_missing_handling():
    df = pd.DataFrame({
        "date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
        "series_id": ["S1", "S1", "S1", "S1"],
        "target": [0.0, None, 15.0, 0.0],
    })
    mapping = {"date": "date", "series_id": "series_id", "target": "target"}
    cleaned_df, report = clean_canonical_dataset("test-zeros", df, mapping)

    assert report.zero_targets_preserved == 2
    assert report.missing_targets_found == 1
    # Check that missing target was not silently converted to 0
    assert len(cleaned_df) == 3


# 5. Negative Targets Flagging
def test_negative_targets_flagged():
    df = pd.DataFrame({
        "date": ["2024-01-01", "2024-01-02"],
        "series_id": ["SERIES_RETURNS", "SERIES_RETURNS"],
        "target": [10.0, -5.0],
    })
    mapping = {"date": "date", "series_id": "series_id", "target": "target"}
    cleaned_df, report = clean_canonical_dataset("test-negative", df, mapping)

    assert report.negative_targets_flagged == 1
    assert "SERIES_RETURNS" in report.negative_series_affected
    # Values preserved
    assert -5.0 in cleaned_df["target"].values


# 6. Date Gaps Detection
def test_date_gaps_audit():
    df = pd.DataFrame({
        "date": ["2024-01-01", "2024-01-02", "2024-01-10"],  # 8 day jump
        "series_id": ["S1", "S1", "S1"],
        "target": [10.0, 12.0, 14.0],
    })
    mapping = {"date": "date", "series_id": "series_id", "target": "target"}
    _, report = clean_canonical_dataset("test-gaps", df, mapping)

    assert report.gaps_detected_count == 1


# 7. Contextual vs Abnormal Outlier Detection
def test_contextual_outliers():
    # 20 regular days, 1 promo spike, 1 unexplainable abnormal spike
    dates = pd.date_range("2024-01-01", periods=20, freq="D")
    targets = [10.0] * 18 + [100.0, 100.0]
    promos = [0] * 18 + [1, 0]  # First spike has promo, second does not

    df = pd.DataFrame({
        "date": dates,
        "series_id": "S1",
        "target": targets,
        "is_promo": promos,
    })
    mapping = {"date": "date", "series_id": "series_id", "target": "target"}
    _, report = clean_canonical_dataset("test-outliers", df, mapping)

    assert report.outliers_contextual_count == 1
    assert report.outliers_abnormal_count == 1


# 8. Series Quality Feasibility Thresholds (7D, 28D, 90D)
def test_series_quality_feasibility_thresholds():
    # Create 3 series:
    # S_short: 15 days (<28 obs)
    # S_med: 40 days (>=28, <90 obs)
    # S_long: 100 days (>=90, <180 obs)
    df_short = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=15, freq="D"),
        "series_id": "S_SHORT",
        "target": 5.0
    })
    df_med = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=40, freq="D"),
        "series_id": "S_MED",
        "target": 10.0
    })
    df_long = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=100, freq="D"),
        "series_id": "S_LONG",
        "target": 15.0
    })
    full_df = pd.concat([df_short, df_med, df_long], ignore_index=True)
    mapping = {"date": "date", "series_id": "series_id", "target": "target"}

    quality_rep = analyze_series_quality("test-quality-thresholds", full_df, mapping)
    m_map = {m.series_id: m for m in quality_rep.all_series_metrics}

    assert m_map["S_SHORT"].horizon_7d_feasible == False
    assert m_map["S_MED"].horizon_7d_feasible == True
    assert m_map["S_MED"].horizon_28d_feasible == False
    assert m_map["S_LONG"].horizon_28d_feasible == True
    assert m_map["S_LONG"].horizon_90d_feasible == False


# 9. Strictly Chronological Split (Train / Val / Test)
def test_chronological_split():
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    df = pd.DataFrame({
        "date": dates,
        "series_id": "S1",
        "target": 10.0
    })
    mapping = {"date": "date", "series_id": "series_id", "target": "target"}
    split_rep = compute_chronological_splits("test-split", df, mapping, test_horizon_days=28, val_horizon_days=14)

    assert split_rep.test.rows_count == 28
    assert split_rep.val.rows_count == 14
    assert split_rep.train.rows_count == (100 - 28 - 14)
    # Chronological ordering check
    assert split_rep.train.end_date < split_rep.val.start_date
    assert split_rep.val.end_date < split_rep.test.start_date


# 10. Feature Engineering: Calendar, Lags, Rolling per Series Without Leakage
def test_feature_engineering_isolation_and_no_leakage():
    # 2 distinct series
    df1 = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=10, freq="D"),
        "series_id": "S1",
        "target": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    })
    df2 = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=10, freq="D"),
        "series_id": "S2",
        "target": [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
    })
    df = pd.concat([df1, df2], ignore_index=True)
    mapping = {"date": "date", "series_id": "series_id", "target": "target"}

    feat_df = engineer_time_series_features(df, mapping, lag_list=[1], rolling_windows=[3])

    # Check lag_1 for S1 at day 0 is NaN (no past data), day 1 is 1
    s1_rows = feat_df[feat_df["series_id"] == "S1"]
    assert np.isnan(s1_rows["target_lag_1"].iloc[0])
    assert s1_rows["target_lag_1"].iloc[1] == 1.0

    # Crucial cross-series isolation check:
    # First row of S2 must have NaN lag_1, NOT S1's last value (10)!
    s2_rows = feat_df[feat_df["series_id"] == "S2"]
    assert np.isnan(s2_rows["target_lag_1"].iloc[0])
    assert s2_rows["target_lag_1"].iloc[1] == 100.0

    # Rolling mean check: rolling_mean_3 on day 3 should only use days 0, 1, 2 (shifted to prevent leakage)
    # For S1 day 3 (value 4), rolling mean of previous 3 values (1, 2, 3) = 2.0
    assert s1_rows["rolling_mean_3"].iloc[3] == 2.0


# 11. Model Formatters (ARIMA, Prophet, LightGBM, Darts)
def test_model_formatters():
    df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=30, freq="D"),
        "series_id": "S1",
        "target": np.arange(30, dtype=float),
        "is_holiday": [0] * 30
    })
    mapping = {"date": "date", "series_id": "series_id", "target": "target"}

    # ARIMA
    arima_df = prepare_arima_dataset(df, mapping, "S1")
    assert list(arima_df.columns) == ["date", "target"]
    assert len(arima_df) == 30

    # Prophet
    prophet_df = prepare_prophet_dataset(df, mapping, "S1")
    assert "ds" in prophet_df.columns and "y" in prophet_df.columns
    assert "is_holiday" in prophet_df.columns

    # LightGBM
    lgb_df = prepare_lightgbm_dataset(df, mapping)
    assert "target_lag_1" in lgb_df.columns
    assert "calendar_weekday" in lgb_df.columns

    # Darts
    darts_dict = prepare_darts_dataset(df, mapping)
    assert darts_dict["total_series"] == 1
    assert "S1" in darts_dict["series"]


# 12. Endpoints Integration for Phase 3
def test_phase3_api_endpoints():
    csv_bytes = b"""date,series_id,target,promo
2024-01-01,STORE_1,10.0,0
2024-01-01,STORE_1,15.0,1
2024-01-02,STORE_1,20.0,0
2024-01-03,STORE_1,25.0,0
"""
    files = {"file": ("p3_test.csv", io.BytesIO(csv_bytes), "text/csv")}
    up_res = client.post("/api/data/upload", files=files)
    dataset_id = up_res.json()["dataset_id"]

    # 1. Clean endpoint
    clean_res = client.post(f"/api/data/{dataset_id}/clean")
    assert clean_res.status_code == 200
    clean_data = clean_res.json()
    assert clean_data["conflicts_resolved"] == 1
    assert clean_data["cleaned_rows"] == 3

    # 2. Cleaning report endpoint
    rep_res = client.get(f"/api/data/{dataset_id}/cleaning-report")
    assert rep_res.status_code == 200
    assert rep_res.json()["cleaned_rows"] == 3

    # 3. Series quality endpoint
    sq_res = client.get(f"/api/data/{dataset_id}/series-quality")
    assert sq_res.status_code == 200
    assert sq_res.json()["total_series"] == 1

    # 4. Chronological splits endpoint
    sp_res = client.get(f"/api/data/{dataset_id}/splits?test_horizon=1&val_horizon=1")
    assert sp_res.status_code == 200
    assert sp_res.json()["split_strategy"] == "Strict Chronological Cutoff (Train -> Validation -> Test)"

    # 5. Preprocessing status endpoint
    st_res = client.get(f"/api/data/{dataset_id}/preprocessing-status")
    assert st_res.status_code == 200
    assert st_res.json()["status"] == PipelineStatus.READY_FOR_MODEL_TRAINING.value

    # 6. Engineered features preview endpoint
    ef_res = client.get(f"/api/data/{dataset_id}/engineered-features")
    assert ef_res.status_code == 200
    assert "target_lag_1" in ef_res.json()["feature_columns"]
