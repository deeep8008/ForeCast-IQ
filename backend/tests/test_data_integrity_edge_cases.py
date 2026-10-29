"""
Data Integrity and Edge-Case Preprocessing Pipeline Regression Suite
Validates ForecastIQ's Upload Dataset, Data Cleaning, and Forecast Readiness pipeline
using 03_edge_case_retail.csv
"""
import os
from pathlib import Path
import pytest
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.data.loader import load_csv_from_bytes, detect_candidate_columns
from app.data.cleaner import (
    clean_canonical_dataset,
    compute_chronological_splits,
    evaluate_dataset_readiness,
    CLEANED_DATASET_STORE,
)

client = TestClient(app)

EDGE_CASE_CSV_PATH = Path("C:/Users/BHARGAV709/Downloads/03_edge_case_retail.csv")


@pytest.fixture(scope="module")
def raw_edge_case_df():
    """Load the edge case dataset from disk."""
    if not EDGE_CASE_CSV_PATH.exists():
        pytest.skip(f"Missing edge case CSV at {EDGE_CASE_CSV_PATH}")
    df = pd.read_csv(EDGE_CASE_CSV_PATH)
    return df


def test_edge_case_raw_file_characteristics(raw_edge_case_df):
    """
    Assert:
    - the raw data has exactly 625 rows,
    - the original file has exactly one zero target,
    - there is one missing target, one negative target, and one malformed date,
    - exact duplicates and conflicting series/date records are present as expected.
    """
    df = raw_edge_case_df
    assert len(df) == 625, f"Expected 625 rows in raw file, got {len(df)}"

    # Exact one malformed date
    parsed_dates = pd.to_datetime(df["date"], errors="coerce")
    malformed_date_count = int(parsed_dates.isna().sum())
    assert malformed_date_count == 1, f"Expected 1 malformed date, got {malformed_date_count}"
    assert df.loc[parsed_dates.isna(), "date"].iloc[0] == "not-a-date"

    # Numeric target inspection
    num_target = pd.to_numeric(df["target"], errors="coerce")
    missing_target_count = int(num_target.isna().sum())
    assert missing_target_count == 1, f"Expected 1 missing target, got {missing_target_count}"

    valid_targets = num_target.dropna()
    zero_target_count = int((valid_targets == 0.0).sum())
    assert zero_target_count == 1, f"Expected exactly 1 raw zero target, got {zero_target_count}"

    negative_target_count = int((valid_targets < 0.0).sum())
    assert negative_target_count == 1, f"Expected exactly 1 raw negative target, got {negative_target_count}"

    # Exact duplicate row
    exact_duplicates = int(df.duplicated().sum())
    assert exact_duplicates == 1, f"Expected exactly 1 duplicate row, got {exact_duplicates}"

    # Conflicting series + date records (after dropping exact duplicates, invalid dates, and missing targets)
    df_no_exact = df.drop_duplicates()
    valid_mask = pd.to_datetime(df_no_exact["date"], errors="coerce").notna() & pd.to_numeric(df_no_exact["target"], errors="coerce").notna()
    df_valid = df_no_exact[valid_mask].copy()
    dup_keys = df_valid.duplicated(subset=["series_id", "date"], keep=False)
    assert int(dup_keys.sum()) == 2, f"Expected 2 rows forming 1 conflicting group, got {int(dup_keys.sum())}"


def test_edge_case_cleaning_pipeline_reconciliation(raw_edge_case_df):
    """
    Test that cleaning pipeline:
    - removes 1 exact duplicate,
    - excludes 1 invalid date,
    - excludes 1 missing target without converting it to 0,
    - preserves exactly 1 genuine zero target,
    - resolves 1 conflicting group via additive SUM,
    - flags 1 negative target for review while keeping it model-eligible,
    - produces exactly 621 cleaned rows,
    - reconciles raw_row_count (625) -> cleaned_row_count (621).
    """
    df = raw_edge_case_df
    mapping = detect_candidate_columns(list(df.columns))
    cleaned_df, report = clean_canonical_dataset(
        dataset_id="test-edge-case-recon",
        df=df,
        mapping=mapping,
        additive_aggregation=True,
        target_type="additive",
    )

    # Assert explicit reconciliation counters
    assert report.raw_row_count == 625
    assert report.exact_duplicate_rows_removed == 1
    assert report.invalid_date_rows_excluded == 1
    assert report.missing_target_rows_excluded_or_imputed == 1
    assert report.conflicting_observation_groups_resolved == 1
    assert report.conflicts_resolved == 1
    assert report.cleaned_row_count == 621
    assert report.eligible_for_training_row_count == 621
    assert len(cleaned_df) == 621

    # Exact reconciliation formula: 625 - 1 (exact dup) - 1 (invalid date) - 1 (missing target) - 1 (conflict aggregation) = 621
    reconciled_total = (
        report.raw_row_count
        - report.exact_duplicate_rows_removed
        - report.invalid_date_rows_excluded
        - report.missing_target_rows_excluded_or_imputed
        - report.conflicts_resolved
    )
    assert reconciled_total == report.cleaned_row_count == 621

    # Assert zero-demand and negative target preservation
    assert report.zero_targets_preserved == 1, f"Expected 1 zero preserved, got {report.zero_targets_preserved}"
    assert report.negative_targets_flagged == 1, f"Expected 1 negative flagged, got {report.negative_targets_flagged}"
    assert (cleaned_df["target"] == 0).sum() == 1
    assert (cleaned_df["target"] < 0).sum() == 1

    # Conflicting target values resolved by SUM: 11.78 + 18.78 = 30.56 on 2025-03-15
    conflicted_row = cleaned_df[
        (cleaned_df["series_id"] == "STORE_A_SKU_001")
        & (cleaned_df["date"] == pd.Timestamp("2025-03-15"))
    ]
    assert len(conflicted_row) == 1
    assert round(float(conflicted_row["target"].iloc[0]), 2) == 30.56


def test_edge_case_chronological_splits_and_leakage(raw_edge_case_df):
    """
    Test temporal splits on cleaned data:
    - Train + Validation + Test counts strictly reconcile to cleaned_row_count (621).
    - Splits do not overlap.
    - No future data leaks into training.
    - Test horizon (28 days) and validation horizon (14 days) are strictly respected.
    """
    df = raw_edge_case_df
    mapping = detect_candidate_columns(list(df.columns))
    cleaned_df, cleaning_report = clean_canonical_dataset(
        dataset_id="test-edge-case-splits",
        df=df,
        mapping=mapping,
    )

    split_report = compute_chronological_splits(
        dataset_id="test-edge-case-splits",
        df=cleaned_df,
        mapping=mapping,
        test_horizon_days=28,
        val_horizon_days=14,
    )

    train_count = split_report.train_row_count
    val_count = split_report.validation_row_count
    test_count = split_report.test_row_count

    # Assert exact row counts
    assert train_count == 538
    assert val_count == 28
    assert test_count == 55
    assert train_count + val_count + test_count == 621
    assert train_count + val_count + test_count == cleaning_report.cleaned_row_count

    # Assert strict chronological boundary order (no future leakage)
    train_end = pd.Timestamp(split_report.train.end_date)
    val_start = pd.Timestamp(split_report.val.start_date)
    val_end = pd.Timestamp(split_report.val.end_date)
    test_start = pd.Timestamp(split_report.test.start_date)

    assert train_end < val_start, f"Train end ({train_end}) must precede val start ({val_start})"
    assert val_end < test_start, f"Val end ({val_end}) must precede test start ({test_start})"

    # Verify no series date overlaps between train, val, test
    date_col = mapping["date"]
    all_dates = pd.to_datetime(cleaned_df[date_col]).sort_values().unique()
    train_dates = set(pd.to_datetime(all_dates[all_dates <= train_end]))
    val_dates = set(pd.to_datetime(all_dates[(all_dates >= val_start) & (all_dates <= val_end)]))
    test_dates = set(pd.to_datetime(all_dates[all_dates >= test_start]))

    assert len(train_dates.intersection(val_dates)) == 0, "Train and Val dates must not overlap"
    assert len(val_dates.intersection(test_dates)) == 0, "Val and Test dates must not overlap"
    assert len(train_dates.intersection(test_dates)) == 0, "Train and Test dates must not overlap"


def test_api_splits_endpoint_uses_cleaned_data(raw_edge_case_df):
    """
    Test that GET /data/{dataset_id}/splits endpoint automatically
    computes splits on cleaned data even if /clean hasn't been called yet.
    """
    csv_bytes = raw_edge_case_df.to_csv(index=False).encode("utf-8")
    dataset_id, _ = load_csv_from_bytes(csv_bytes, filename="edge_case_test.csv")

    # Clear CLEANED_DATASET_STORE for this dataset to verify fallback cleaning
    if dataset_id in CLEANED_DATASET_STORE:
        del CLEANED_DATASET_STORE[dataset_id]

    res = client.get(f"/api/data/{dataset_id}/splits?test_horizon=28&val_horizon=14")
    assert res.status_code == 200
    data = res.json()

    total_split_rows = data["train_row_count"] + data["validation_row_count"] + data["test_row_count"]
    assert total_split_rows == 621, f"Expected 621 total split rows, got {total_split_rows}"
    assert data["train_row_count"] == 538
    assert data["validation_row_count"] == 28
    assert data["test_row_count"] == 55


def test_normal_valid_csv_continues_to_work():
    """Verify standard valid CSV works seamlessly without regressions."""
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    df = pd.DataFrame({
        "date": dates,
        "series_id": ["STORE_A"] * 100,
        "target": np.random.uniform(10, 50, size=100).round(2),
    })
    mapping = {"date": "date", "series_id": "series_id", "target": "target"}
    cleaned_df, report = clean_canonical_dataset("test-normal", df, mapping)

    assert report.raw_row_count == 100
    assert report.cleaned_row_count == 100
    assert report.exact_duplicate_rows_removed == 0
    assert report.invalid_date_rows_excluded == 0
    assert report.missing_target_rows_excluded_or_imputed == 0
    assert report.conflicts_resolved == 0

    splits = compute_chronological_splits("test-normal", cleaned_df, mapping, test_horizon_days=28, val_horizon_days=14)
    assert splits.train_row_count + splits.validation_row_count + splits.test_row_count == 100
