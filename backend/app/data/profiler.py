"""
Data Profiler Module using Pandas
ForecastIQ Backend
"""
from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd
from .schema import DatasetProfile, TargetStatistics, DateRangeProfile


def detect_series_frequency(df: pd.DataFrame, date_col: str, series_col: str) -> Tuple[str, str]:
    """
    Detect temporal observation frequency per series.
    Returns (detected_frequency, warning_message).
    Primary supported frequency for multi-horizon enterprise forecasting is DAILY ('D').
    """
    if not date_col or date_col not in df.columns:
        return "Unknown", "Missing date column for frequency detection."

    try:
        # Convert to datetime temporarily
        dates = pd.to_datetime(df[date_col], errors="coerce").dropna()
        if len(dates) < 2:
            return "Unknown", "Insufficient valid date observations to infer cadence."

        # If series_col exists, evaluate intervals within top series
        if series_col and series_col in df.columns:
            top_series = df[series_col].value_counts().index[:5]
            intervals_days = []
            for s_id in top_series:
                s_dates = pd.to_datetime(df[df[series_col] == s_id][date_col], errors="coerce").dropna().sort_values()
                if len(s_dates) >= 2:
                    diffs = s_dates.diff().dt.total_seconds().div(86400).dropna()
                    median_diff = diffs.median()
                    if median_diff > 0:
                        intervals_days.append(median_diff)

            if intervals_days:
                avg_interval = float(np.median(intervals_days))
            else:
                s_dates = dates.sort_values().drop_duplicates()
                diffs = s_dates.diff().dt.total_seconds().div(86400).dropna()
                avg_interval = float(diffs.median()) if not diffs.empty else 1.0
        else:
            s_dates = dates.sort_values().drop_duplicates()
            diffs = s_dates.diff().dt.total_seconds().div(86400).dropna()
            avg_interval = float(diffs.median()) if not diffs.empty else 1.0

        if 0.8 <= avg_interval <= 1.2:
            return "Daily (D)", ""
        elif 6.0 <= avg_interval <= 8.0:
            return "Weekly (W)", "Detected weekly frequency. Primary multi-horizon models (7D/28D/90D) are optimized for daily observations."
        elif 27.0 <= avg_interval <= 32.0:
            return "Monthly (M)", "Detected monthly frequency. Short 7-day operational horizon is not applicable for monthly data."
        elif 0.03 <= avg_interval <= 0.05:
            return "Hourly (H)", "Detected hourly frequency. High-frequency aggregation may be required for 90-day multi-horizon forecasting."
        else:
            return f"Irregular (~{avg_interval:.1f} days interval)", "Detected irregular time intervals. Irregular series require calendar alignment or resampling."
    except Exception as e:
        return "Unknown", f"Frequency detection encountered an error: {str(e)}"


def compute_target_statistics(df: pd.DataFrame, target_col: str) -> TargetStatistics:
    """Calculate thorough distribution statistics for the numerical target variable."""
    if not target_col or target_col not in df.columns:
        return TargetStatistics(count=0)

    numeric_target = pd.to_numeric(df[target_col], errors="coerce")
    valid_series = numeric_target.dropna()

    if valid_series.empty:
        return TargetStatistics(count=0)

    zero_count = int((valid_series == 0).sum())
    negative_count = int((valid_series < 0).sum())

    return TargetStatistics(
        count=int(valid_series.count()),
        mean=round(float(valid_series.mean()), 4),
        std=round(float(valid_series.std()), 4) if len(valid_series) > 1 else 0.0,
        min=round(float(valid_series.min()), 4),
        q25=round(float(valid_series.quantile(0.25)), 4),
        median=round(float(valid_series.median()), 4),
        q75=round(float(valid_series.quantile(0.75)), 4),
        max=round(float(valid_series.max()), 4),
        zero_count=zero_count,
        negative_count=negative_count,
    )


def profile_dataset(
    dataset_id: str,
    df: pd.DataFrame,
    filename: str,
    mapping: Dict[str, Any]
) -> DatasetProfile:
    """
    Perform deep statistical profiling across all columns of the dataset.
    """
    rows_count = int(len(df))
    cols_count = int(len(df.columns))
    col_names = [str(c) for c in df.columns]

    date_col = mapping.get("date", "")
    series_col = mapping.get("series_id", "")
    target_col = mapping.get("target", "")

    # Date Range calculation
    date_range = DateRangeProfile()
    if date_col and date_col in df.columns:
        dates = pd.to_datetime(df[date_col], errors="coerce").dropna().sort_values()
        if not dates.empty:
            start_d = dates.iloc[0].strftime("%Y-%m-%d")
            end_d = dates.iloc[-1].strftime("%Y-%m-%d")
            total_days = int((dates.iloc[-1] - dates.iloc[0]).days) + 1
            date_range = DateRangeProfile(
                start_date=start_d,
                end_date=end_d,
                total_days=total_days
            )

    # Frequency
    detected_freq, _ = detect_series_frequency(df, date_col, series_col)

    # Unique series count
    unique_series = 0
    if series_col and series_col in df.columns:
        unique_series = int(df[series_col].nunique(dropna=True))

    # Target statistics
    target_stats = compute_target_statistics(df, target_col)

    # Missing counts
    missing_cells = int(df.isna().sum().sum())
    total_cells = max(1, rows_count * cols_count)
    missing_pct = round(float((missing_cells / total_cells) * 100), 2)

    # Duplicate rows
    duplicate_rows = int(df.duplicated().sum())

    # Conflicting series_id + date records
    conflicting_records = 0
    if date_col in df.columns and series_col in df.columns and date_col and series_col:
        sub_df = df[[series_col, date_col]].dropna()
        conflicting_records = int(sub_df.duplicated().sum())

    # Identify numerical, categorical, and identifier columns
    numerical_cols: List[str] = []
    categorical_cols: List[str] = []
    identifier_cols: List[str] = []

    for col in df.columns:
        if col in (date_col, target_col):
            continue
        col_series = df[col]
        nunique = col_series.nunique(dropna=True)

        if pd.api.types.is_numeric_dtype(col_series):
            numerical_cols.append(str(col))
        elif nunique > 0 and (nunique == rows_count or "id" in col.lower() or "code" in col.lower()):
            identifier_cols.append(str(col))
        else:
            categorical_cols.append(str(col))

    return DatasetProfile(
        dataset_id=dataset_id,
        filename=filename,
        rows_count=rows_count,
        columns_count=cols_count,
        column_names=col_names,
        detected_frequency=detected_freq,
        unique_series_count=unique_series,
        date_range=date_range,
        target_statistics=target_stats,
        missing_values_total=missing_cells,
        missing_values_pct=missing_pct,
        duplicate_rows_count=duplicate_rows,
        conflicting_records_count=conflicting_records,
        numerical_columns=numerical_cols,
        categorical_columns=categorical_cols,
        identifier_columns=identifier_cols,
    )
