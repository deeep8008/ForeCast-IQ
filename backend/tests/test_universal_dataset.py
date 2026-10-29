"""
Comprehensive Backend Tests for Universal Dataset Engine (Phase 2)
Tests 1-14:
1. Valid canonical CSV
2. Missing date
3. Missing series_id
4. Missing target
5. Invalid date
6. Invalid target
7. Empty required field
8. Exact duplicate rows
9. Duplicate series_id + date
10. Date gaps
11. Frequency detection
12. Feature classification
13. M5 adapter
14. Dataset readiness
"""
import pytest
import pandas as pd
import numpy as np
from app.data.schema import (
    ReadinessStatus,
    ColumnClassification,
    MANDATORY_CANONICAL_FIELDS,
)
from app.data.loader import load_csv_from_bytes, detect_candidate_columns
from app.data.profiler import profile_dataset, detect_series_frequency
from app.data.validator import validate_schema_and_series
from app.features.analyzer import analyze_features
from app.data.adapters.m5_adapter import M5Adapter
from app.data.cleaner import evaluate_dataset_readiness, clean_canonical_dataset


# 1. Valid canonical CSV
def test_valid_canonical_csv():
    csv_bytes = b"""date,series_id,target,store_id,price
2024-01-01,STORE_1_ITEM_A,42.0,STORE_1,2.50
2024-01-02,STORE_1_ITEM_A,45.0,STORE_1,2.50
2024-01-03,STORE_1_ITEM_A,50.0,STORE_1,2.50
2024-01-04,STORE_1_ITEM_A,48.0,STORE_1,2.50
"""
    dataset_id, df = load_csv_from_bytes(csv_bytes, "valid_test.csv")
    mapping = detect_candidate_columns(list(df.columns))
    
    assert mapping["date"] == "date"
    assert mapping["series_id"] == "series_id"
    assert mapping["target"] == "target"
    
    val_report, summary = validate_schema_and_series(dataset_id, df, mapping)
    assert val_report.status == ReadinessStatus.READY
    assert len(val_report.errors) == 0
    assert summary.total_series == 1


# 2. Missing date
def test_missing_date():
    csv_bytes = b"""series_id,target,price
STORE_1_ITEM_A,42.0,2.50
STORE_1_ITEM_A,45.0,2.50
"""
    dataset_id, df = load_csv_from_bytes(csv_bytes, "missing_date.csv")
    mapping = detect_candidate_columns(list(df.columns))
    val_report, _ = validate_schema_and_series(dataset_id, df, mapping)
    
    assert "date" in val_report.missing_mandatory_fields
    assert any("date" in err.lower() for err in val_report.errors)
    assert val_report.status == ReadinessStatus.INVALID


# 3. Optional series_id (Single Series vs Ambiguous Multi-Series)
def test_optional_series_id_single_series():
    csv_bytes = b"""date,target,price
2024-01-01,42.0,2.50
2024-01-02,45.0,2.50
2024-01-03,48.0,2.50
"""
    dataset_id, df = load_csv_from_bytes(csv_bytes, "single_series.csv")
    mapping = detect_candidate_columns(list(df.columns))
    val_report, summary = validate_schema_and_series(dataset_id, df, mapping)
    
    assert "date" not in val_report.missing_mandatory_fields
    assert "target" not in val_report.missing_mandatory_fields
    assert len(val_report.missing_mandatory_fields) == 0
    assert val_report.status == ReadinessStatus.READY
    assert summary.total_series == 1
    assert summary.sample_series_quality[0].series_id == "default_series"


def test_missing_series_id_with_ambiguous_dates():
    # Multiple distinct records on the same date without series_id must NOT be silently combined
    csv_bytes = b"""date,target,price
2024-01-01,42.0,2.50
2024-01-01,15.0,3.00
2024-01-02,45.0,2.50
"""
    dataset_id, df = load_csv_from_bytes(csv_bytes, "ambiguous_series.csv")
    mapping = detect_candidate_columns(list(df.columns))
    val_report, _ = validate_schema_and_series(dataset_id, df, mapping)
    
    assert any("ambiguous" in err.lower() for err in val_report.errors)
    assert val_report.status == ReadinessStatus.NEEDS_ATTENTION


# 4. Missing target
def test_missing_target():
    csv_bytes = b"""date,series_id,price
2024-01-01,STORE_1_ITEM_A,2.50
2024-01-02,STORE_1_ITEM_A,2.50
"""
    dataset_id, df = load_csv_from_bytes(csv_bytes, "missing_target.csv")
    mapping = detect_candidate_columns(list(df.columns))
    val_report, _ = validate_schema_and_series(dataset_id, df, mapping)
    
    assert "target" in val_report.missing_mandatory_fields
    assert any("target" in err.lower() for err in val_report.errors)
    assert val_report.status == ReadinessStatus.INVALID


# 5. Invalid date
def test_invalid_date():
    csv_bytes = b"""date,series_id,target
2024-01-01,STORE_1_ITEM_A,40.0
NOT_A_REAL_DATE,STORE_1_ITEM_A,45.0
2024-01-03,STORE_1_ITEM_A,50.0
"""
    dataset_id, df = load_csv_from_bytes(csv_bytes, "invalid_date.csv")
    mapping = detect_candidate_columns(list(df.columns))
    val_report, _ = validate_schema_and_series(dataset_id, df, mapping)
    
    assert val_report.invalid_dates_count == 1
    assert any("unparseable" in err.lower() or "malformed" in err.lower() for err in val_report.errors)
    assert val_report.status == ReadinessStatus.NEEDS_ATTENTION


# 6. Invalid target
def test_invalid_target():
    csv_bytes = b"""date,series_id,target
2024-01-01,STORE_1_ITEM_A,40.0
2024-01-02,STORE_1_ITEM_A,NOT_A_NUMBER
2024-01-03,STORE_1_ITEM_A,50.0
"""
    dataset_id, df = load_csv_from_bytes(csv_bytes, "invalid_target.csv")
    mapping = detect_candidate_columns(list(df.columns))
    val_report, _ = validate_schema_and_series(dataset_id, df, mapping)
    
    assert val_report.invalid_target_values_count == 1
    assert any("non-numeric" in err.lower() for err in val_report.errors)
    assert val_report.status == ReadinessStatus.NEEDS_ATTENTION


# 7. Empty required field
def test_empty_required_field():
    csv_bytes = b"""date,series_id,target
2024-01-01,,40.0
,STORE_1_ITEM_A,45.0
2024-01-03,STORE_1_ITEM_A,
"""
    dataset_id, df = load_csv_from_bytes(csv_bytes, "empty_fields.csv")
    mapping = detect_candidate_columns(list(df.columns))
    val_report, _ = validate_schema_and_series(dataset_id, df, mapping)
    
    assert any("empty or null series" in err.lower() for err in val_report.errors)
    assert any("empty or blank timestamp" in err.lower() for err in val_report.errors)


# 8. Exact duplicate rows
def test_exact_duplicate_rows():
    csv_bytes = b"""date,series_id,target
2024-01-01,STORE_1_ITEM_A,40.0
2024-01-01,STORE_1_ITEM_A,40.0
2024-01-02,STORE_1_ITEM_A,45.0
"""
    dataset_id, df = load_csv_from_bytes(csv_bytes, "exact_dup.csv")
    mapping = detect_candidate_columns(list(df.columns))
    val_report, _ = validate_schema_and_series(dataset_id, df, mapping)
    
    assert val_report.exact_duplicate_rows == 1
    assert any("exact duplicate" in warn.lower() for warn in val_report.warnings)


# 9. Duplicate series_id + date (conflict)
def test_duplicate_series_date_conflict():
    csv_bytes = b"""date,series_id,target
2024-01-01,STORE_1_ITEM_A,40.0
2024-01-01,STORE_1_ITEM_A,95.0
2024-01-02,STORE_1_ITEM_A,45.0
"""
    dataset_id, df = load_csv_from_bytes(csv_bytes, "conflict_dup.csv")
    mapping = detect_candidate_columns(list(df.columns))
    val_report, _ = validate_schema_and_series(dataset_id, df, mapping)
    
    assert val_report.conflicting_series_date_records == 1
    assert any("conflicting record" in err.lower() for err in val_report.errors)


# 10. Date gaps
def test_date_gaps_detection():
    csv_bytes = b"""date,series_id,target
2024-01-01,STORE_1_ITEM_A,40.0
2024-01-02,STORE_1_ITEM_A,45.0
2024-01-08,STORE_1_ITEM_A,50.0
"""
    dataset_id, df = load_csv_from_bytes(csv_bytes, "date_gaps.csv")
    mapping = detect_candidate_columns(list(df.columns))
    val_report, series_summary = validate_schema_and_series(dataset_id, df, mapping)
    
    assert series_summary.series_with_gaps == 1
    assert any("temporal date gaps" in warn.lower() for warn in val_report.warnings)


# 11. Frequency detection
def test_frequency_detection():
    # Daily
    daily_df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=10, freq="D"),
        "series_id": "SERIES_1",
        "target": 10
    })
    freq_daily, _ = detect_series_frequency(daily_df, "date", "series_id")
    assert "Daily" in freq_daily

    # Weekly
    weekly_df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=10, freq="W"),
        "series_id": "SERIES_1",
        "target": 10
    })
    freq_weekly, warn_weekly = detect_series_frequency(weekly_df, "date", "series_id")
    assert "Weekly" in freq_weekly
    assert "Detected weekly frequency" in warn_weekly


# 12. Feature classification
def test_feature_classification():
    df = pd.DataFrame({
        "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
        "series_id": ["S1", "S1", "S1"],
        "target": [10.0, 15.0, 20.0],
        "holiday_event": ["Easter", "", ""],
        "future_demand_test": [12.0, 14.0, 16.0],
        "constant_col": [1, 1, 1],
        "store_id": ["STORE_A", "STORE_A", "STORE_A"],
        "price": [2.99, 2.99, 1.99]
    })
    mapping = {
        "date": "date",
        "series_id": "series_id",
        "target": "target"
    }
    features = analyze_features(df, mapping)
    class_map = {f.name: f.classification for f in features}

    assert class_map["date"] == ColumnClassification.TIME
    assert class_map["target"] == ColumnClassification.TARGET
    assert class_map["series_id"] == ColumnClassification.SERIES_ID
    assert class_map["holiday_event"] == ColumnClassification.KNOWN_FUTURE
    assert class_map["future_demand_test"] == ColumnClassification.POTENTIAL_LEAKAGE
    assert class_map["constant_col"] == ColumnClassification.CONSTANT
    assert class_map["price"] == ColumnClassification.POTENTIALLY_USEFUL


# 13. M5 adapter
def test_m5_adapter():
    m5_sales = pd.DataFrame({
        "id": ["HOBBIES_1_001_CA_1_validation", "HOBBIES_1_002_CA_1_validation"],
        "item_id": ["HOBBIES_1_001", "HOBBIES_1_002"],
        "dept_id": ["HOBBIES_1", "HOBBIES_1"],
        "cat_id": ["HOBBIES", "HOBBIES"],
        "store_id": ["CA_1", "CA_1"],
        "state_id": ["CA", "CA"],
        "d_1": [0, 1],
        "d_2": [2, 0],
        "d_3": [1, 3]
    })
    calendar_df = pd.DataFrame({
        "d": ["d_1", "d_2", "d_3"],
        "date": ["2011-01-29", "2011-01-30", "2011-01-31"],
        "wm_yr_wk": [11101, 11101, 11101],
        "event_name_1": ["NewYear", None, None]
    })

    canonical_df = M5Adapter.transform_sales_wide_to_canonical(
        sales_df=m5_sales,
        calendar_df=calendar_df,
        max_series=2,
        max_days=3
    )

    assert "date" in canonical_df.columns
    assert "series_id" in canonical_df.columns
    assert "target" in canonical_df.columns
    assert "store_id" in canonical_df.columns
    assert "category" in canonical_df.columns
    assert len(canonical_df) == 6  # 2 series * 3 days
    assert canonical_df["series_id"].iloc[0] == "HOBBIES_1_001_CA_1"


# 14. Dataset readiness
def test_dataset_readiness_evaluation():
    # Construct 45-day daily series
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    df = pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "series_id": "SERIES_CA_1",
        "target": np.random.randint(10, 50, size=60),
        "price": 2.50
    })
    mapping = {"date": "date", "series_id": "series_id", "target": "target"}
    report = evaluate_dataset_readiness("test-id-123", df, "retail_60d.csv", mapping)

    assert report.status == ReadinessStatus.READY
    assert report.profile.rows_count == 60
    assert report.profile.unique_series_count == 1
    assert report.supported_horizons["h7"].status == "Supported"
    assert report.supported_horizons["h28"].status == "Borderline" or report.supported_horizons["h28"].status == "Supported"
    assert len(report.readiness_checklist) == 5
    assert all(item["passed"] for item in report.readiness_checklist)


# 15. Single-series CSV with only date and target (no series_id)
def test_upload_and_clean_single_series_only_date_target():
    dates = pd.date_range("2024-01-01", periods=45, freq="D")
    csv_str = "date,target\n" + "\n".join(f"{d.strftime('%Y-%m-%d')},{i + 10}" for i, d in enumerate(dates))
    dataset_id, df = load_csv_from_bytes(csv_str.encode("utf-8"), "univariate.csv")
    mapping = detect_candidate_columns(list(df.columns))

    val_report, summary = validate_schema_and_series(dataset_id, df, mapping)
    assert val_report.status == ReadinessStatus.READY
    assert len(val_report.errors) == 0

    cleaned_df, clean_rep = clean_canonical_dataset(dataset_id, df, mapping)
    assert "series_id" in cleaned_df.columns
    assert (cleaned_df["series_id"] == "default_series").all()
    assert clean_rep.cleaned_rows == 45


# 16. Composite identifier generation from store_id + item_id
def test_composite_identifier_generation():
    csv_bytes = b"""date,store_id,item_id,target,price
2024-01-01,STORE_1,ITEM_A,10,2.5
2024-01-02,STORE_1,ITEM_A,12,2.5
2024-01-01,STORE_1,ITEM_B,20,3.0
2024-01-02,STORE_1,ITEM_B,22,3.0
"""
    dataset_id, df = load_csv_from_bytes(csv_bytes, "composite.csv")
    mapping = detect_candidate_columns(list(df.columns))
    assert "store_id" in mapping["candidate_entity_columns"]
    assert "item_id" in mapping["candidate_entity_columns"]
    assert "price" not in mapping["candidate_entity_columns"]

    # Provide composite keys mapping
    mapping["composite_series_keys"] = ["store_id", "item_id"]
    val_report, summary = validate_schema_and_series(dataset_id, df, mapping)
    assert val_report.status == ReadinessStatus.READY
    assert summary.total_series == 2

    cleaned_df, clean_rep = clean_canonical_dataset(dataset_id, df, mapping)
    assert "series_id" in cleaned_df.columns
    unique_series = set(cleaned_df["series_id"].unique())
    assert unique_series == {"STORE_1__ITEM_A", "STORE_1__ITEM_B"}


# 17. Phase 2: Single series with 1,000 observations produces exactly 800 train and 200 test observations
def test_80_20_split_1000_observations():
    from app.data.cleaner import split_series_chronological_80_20, split_dataset_chronological_80_20, compute_chronological_splits

    dates = pd.date_range("2020-01-01", periods=1000, freq="D")
    df = pd.DataFrame({
        "date": dates,
        "series_id": "SERIES_1K",
        "target": np.random.uniform(10, 100, 1000)
    })
    mapping = {"date": "date", "series_id": "series_id", "target": "target"}

    tr, te = split_series_chronological_80_20(df, time_col="date", train_ratio=0.8)
    assert len(tr) == 800
    assert len(te) == 200
    assert len(tr) + len(te) == 1000

    # Test through compute_chronological_splits
    report = compute_chronological_splits("ds_1k", df, mapping, use_80_20_ratio=True)
    assert report.train_row_count == 800
    assert report.test_row_count == 200
    assert report.split_ratio == "80:20"


# 18. Phase 2: Strict chronological order: all training dates precede all test dates
def test_80_20_split_chronological_order():
    from app.data.cleaner import split_series_chronological_80_20

    dates = pd.date_range("2023-01-01", periods=100, freq="D")
    df = pd.DataFrame({
        "date": dates,
        "series_id": "SERIES_CHRONO",
        "target": np.arange(100)
    })
    # Intentionally shuffle input DataFrame to verify function sorts chronologically before splitting
    shuffled_df = df.sample(frac=1.0, random_state=42).reset_index(drop=True)

    tr, te = split_series_chronological_80_20(shuffled_df, time_col="date", train_ratio=0.8)
    assert len(tr) == 80
    assert len(te) == 20
    assert tr["date"].max() < te["date"].min()
    assert (tr["date"].diff().dropna() > pd.Timedelta(0)).all()
    assert (te["date"].diff().dropna() > pd.Timedelta(0)).all()


# 19. Phase 2: Split rounding policy when observation counts are not divisible by five
def test_80_20_split_not_divisible_by_five():
    from app.data.cleaner import split_series_chronological_80_20

    # 101 observations: 101 * 0.8 = 80.8 -> round to 81 train, 20 test
    df_101 = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=101, freq="D"),
        "target": np.ones(101)
    })
    tr_101, te_101 = split_series_chronological_80_20(df_101, time_col="date", train_ratio=0.8)
    assert len(tr_101) == 81
    assert len(te_101) == 20
    assert len(tr_101) + len(te_101) == 101

    # 103 observations: 103 * 0.8 = 82.4 -> round to 82 train, 21 test
    df_103 = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=103, freq="D"),
        "target": np.ones(103)
    })
    tr_103, te_103 = split_series_chronological_80_20(df_103, time_col="date", train_ratio=0.8)
    assert len(tr_103) == 82
    assert len(te_103) == 21
    assert len(tr_103) + len(te_103) == 103

    # 7 observations: 7 * 0.8 = 5.6 -> round to 6 train, 1 test
    df_7 = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=7, freq="D"),
        "target": np.ones(7)
    })
    tr_7, te_7 = split_series_chronological_80_20(df_7, time_col="date", train_ratio=0.8)
    assert len(tr_7) == 6
    assert len(te_7) == 1


# 20. Phase 2: Dataset without uploaded series_id uses internal default_series correctly
def test_80_20_split_internal_default_series():
    from app.data.cleaner import split_dataset_chronological_80_20, compute_chronological_splits

    dates = pd.date_range("2023-01-01", periods=50, freq="D")
    df = pd.DataFrame({
        "date": dates,
        "target": np.random.uniform(5, 50, 50)
    })
    mapping = {"date": "date", "target": "target"}

    tr, te = split_dataset_chronological_80_20(df, mapping=mapping, train_ratio=0.8)
    assert len(tr) == 40
    assert len(te) == 10
    assert "series_id" in tr.columns
    assert (tr["series_id"] == "default_series").all()
    assert (te["series_id"] == "default_series").all()

    report = compute_chronological_splits("ds_no_series", df, mapping, use_80_20_ratio=True)
    assert report.train_row_count == 40
    assert report.test_row_count == 10


# 21. Phase 2: Multi-series separation and independent chronological ordering
def test_80_20_split_multi_series_separation():
    from app.data.cleaner import split_dataset_chronological_80_20

    dates = pd.date_range("2023-01-01", periods=50, freq="D")
    df1 = pd.DataFrame({"date": dates, "series_id": "SERIES_A", "target": 10.0})
    df2 = pd.DataFrame({"date": dates, "series_id": "SERIES_B", "target": 20.0})
    combined = pd.concat([df1, df2], ignore_index=True)
    mapping = {"date": "date", "series_id": "series_id", "target": "target"}

    tr, te = split_dataset_chronological_80_20(combined, mapping=mapping, train_ratio=0.8)
    assert len(tr) == 80  # 40 per series * 2
    assert len(te) == 20  # 10 per series * 2

    # Verify per-series temporal integrity
    for s_id in ["SERIES_A", "SERIES_B"]:
        s_tr = tr[tr["series_id"] == s_id]
        s_te = te[te["series_id"] == s_id]
        assert len(s_tr) == 40
        assert len(s_te) == 10
        assert s_tr["date"].max() < s_te["date"].min()


# 22. Phase 2: No future observations leak into training features or preprocessing
def test_no_data_leakage_in_features():
    from app.features.engineer import engineer_time_series_features

    dates = pd.date_range("2023-01-01", periods=10, freq="D")
    df = pd.DataFrame({
        "date": dates,
        "series_id": "S_LEAK_CHECK",
        "target": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    })
    mapping = {"date": "date", "series_id": "series_id", "target": "target"}
    feat_df = engineer_time_series_features(df, mapping, lag_list=[1, 2], rolling_windows=[3])

    # First day target_lag_1 must be NaN (cannot look into nonexistent past or future)
    assert pd.isna(feat_df.loc[0, "target_lag_1"])
    # Day 1 target_lag_1 must be Day 0 target (10.0)
    assert feat_df.loc[1, "target_lag_1"] == 10.0
    # Day 2 target_lag_2 must be Day 0 target (10.0)
    assert feat_df.loc[2, "target_lag_2"] == 10.0
    # 3-day rolling mean shifted by 1 to prevent current-step target leakage:
    # At day 2: shifted past observations are day 0 (10) and day 1 (20) -> mean(10, 20) = 15.0
    assert feat_df.loc[2, "rolling_mean_3"] == 15.0
    # At day 3: shifted past observations are day 0 (10), day 1 (20), day 2 (30) -> mean(10, 20, 30) = 20.0
    assert feat_df.loc[3, "rolling_mean_3"] == 20.0


# 23. Phase 2: Evaluation engine reports split_policy and holdout_80_20_eval
def test_evaluation_engine_80_20_policy():
    from app.evaluation.backtesting import BacktestingEngine

    dates = pd.date_range("2023-01-01", periods=100, freq="D")
    df = pd.DataFrame({
        "date": dates,
        "series_id": "SERIES_EVAL_POLICY",
        "target": np.random.uniform(50, 100, 100)
    })
    mapping = {"date": "date", "series_id": "series_id", "target": "target"}

    eval_res = BacktestingEngine.evaluate_model_on_series(
        dataset_id="DS_EVAL_POL",
        series_id="SERIES_EVAL_POLICY",
        model_name="arima",
        horizon=7,
        series_df=df,
        mapping=mapping,
        n_folds=1,
    )
    assert eval_res["status"] == "SUCCESS"
    assert eval_res["split_policy"] == "80:20_chronological"
    assert "holdout_80_20_eval" in eval_res
    h_eval = eval_res["holdout_80_20_eval"]
    assert h_eval["train_obs"] == 80
    assert h_eval["test_obs"] == 20
    assert h_eval["horizon"] == 7
    assert h_eval["mape"] is not None
    assert h_eval["rmse"] is not None
