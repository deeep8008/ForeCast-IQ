"""
Schema and Series Validation Engine
ForecastIQ Backend
"""
from typing import Dict, Any, List, Tuple
import pandas as pd
import numpy as np
from .schema import (
    ValidationReport,
    ReadinessStatus,
    ColumnMapping,
    SeriesSummary,
    SeriesQualityItem,
    MANDATORY_CANONICAL_FIELDS,
)
from .profiler import detect_series_frequency


def validate_schema_and_series(
    dataset_id: str,
    df: pd.DataFrame,
    mapping: Dict[str, Any]
) -> Tuple[ValidationReport, SeriesSummary]:
    """
    Validate canonical required columns, data types, timestamp conflicts,
    series intervals, date gaps, and value distributions.
    """
    errors: List[str] = []
    warnings: List[str] = []
    missing_mandatory: List[str] = []

    date_col = mapping.get("date") or ""
    series_col = mapping.get("series_id") or ""
    target_col = mapping.get("target") or ""
    composite_keys = mapping.get("composite_series_keys") or []

    # Defensive fallback check for date and target columns
    if not date_col or date_col not in df.columns:
        for cand in ["date", "datetime", "timestamp", "ds", "time", "d", "month", "observation_date", "order_date"]:
            m = next((c for c in df.columns if c.lower() == cand), None)
            if m:
                date_col = m
                break
    if not target_col or target_col not in df.columns:
        for cand in ["weekly_sales", "monthly_sales", "daily_sales", "total_sales", "sales", "target", "demand", "units", "quantity", "val", "value", "revenue", "y", "pjme_mw", "#passengers"]:
            m = next((c for c in df.columns if c.lower() == cand), None)
            if m:
                target_col = m
                break

    # 1. Check Mandatory Column Existence (Only date and target are mandatory inputs)
    if not date_col or date_col not in df.columns:
        missing_mandatory.append("date")
        errors.append("Mandatory column 'date' is missing or unmapped.")

    if not target_col or target_col not in df.columns:
        missing_mandatory.append("target")
        errors.append("Mandatory column 'target' is missing or unmapped.")

    # Counters
    invalid_dates_count = 0
    invalid_target_count = 0
    negative_target_count = 0
    exact_duplicates_count = int(df.duplicated().sum())
    conflicting_records_count = 0

    if exact_duplicates_count > 0:
        warnings.append(f"Detected {exact_duplicates_count} exact duplicate row(s). Deduplication will be applied prior to modeling.")

    # 2. Date Column Validation
    parsed_dates = None
    if date_col and date_col in df.columns:
        date_series = df[date_col]
        # Check empty dates
        empty_dates = int(date_series.isna().sum()) + int((date_series.dropna().astype(str).str.strip() == "").sum())
        if empty_dates > 0:
            errors.append(f"Date column '{date_col}' contains {empty_dates} empty or blank timestamp(s).")

        parsed_dates = pd.to_datetime(date_series, errors="coerce")
        invalid_dates_count = int(parsed_dates.isna().sum()) - int(date_series.isna().sum())
        if invalid_dates_count > 0:
            errors.append(f"Date column '{date_col}' contains {invalid_dates_count} unparseable or malformed date value(s).")

    # 3. Series ID Column / Composite Keys / Single Series Validation
    # Build effective series column representation
    effective_series_name = series_col
    effective_series_series = None

    if composite_keys and all(ck in df.columns for ck in composite_keys):
        effective_series_name = "__composite_series__"
        # Synthesize composite series representation
        effective_series_series = df[composite_keys].astype(str).agg("__".join, axis=1)
    elif series_col and series_col in df.columns:
        effective_series_series = df[series_col]
        empty_series_count = int(effective_series_series.isna().sum()) + int((effective_series_series.dropna().astype(str).str.strip().isin(["", "nan", "none", "null"])).sum())
        if empty_series_count > 0:
            errors.append(f"Series ID column '{series_col}' contains {empty_series_count} empty or null series identifier(s).")
    else:
        # No explicit series_id and no composite keys
        # Check if dataset appears to be single series or ambiguous multi-series
        if date_col in df.columns and parsed_dates is not None:
            # Check for duplicate timestamps in raw dataset (excluding exact duplicates)
            dedup_df = df.drop_duplicates()
            date_counts = dedup_df[date_col].value_counts()
            max_obs_per_date = int(date_counts.max()) if not date_counts.empty else 1
            if max_obs_per_date > 1:
                # Ambiguous duplicate dates detected without an identifier!
                conflicting_dates = int((date_counts > 1).sum())
                errors.append(
                    f"Ambiguous observations detected: {conflicting_dates} timestamp(s) have multiple distinct rows, "
                    "but no 'series_id' or entity identification columns (e.g. store_id, item_id) were mapped. "
                    "Please map an identifier or composite keys to prevent incorrectly combining separate time series."
                )
            else:
                # Confirmed single series: assign internal default_series
                effective_series_name = "default_series"
                effective_series_series = pd.Series(["default_series"] * len(df), index=df.index)

    # 4. Target Column Validation
    if target_col and target_col in df.columns:
        target_series = df[target_col]
        # Empty target check
        empty_targets = int(target_series.isna().sum())
        if empty_targets == len(df):
            errors.append(f"Target column '{target_col}' is completely empty across all rows.")
        elif empty_targets > 0:
            warnings.append(f"Target column '{target_col}' has {empty_targets} missing value(s). Missing targets must be interpolated or reviewed.")

        numeric_target = pd.to_numeric(target_series, errors="coerce")
        invalid_target_count = int(numeric_target.isna().sum()) - empty_targets
        if invalid_target_count > 0:
            errors.append(f"Target column '{target_col}' contains {invalid_target_count} non-numeric string value(s).")

        negative_target_count = int((numeric_target < 0).sum())
        if negative_target_count > 0:
            warnings.append(f"Target column '{target_col}' contains {negative_target_count} negative value(s). Confirm whether these represent customer returns or adjustments.")

        # Outlier Detection (IQR Method)
        valid_targets = numeric_target.dropna()
        if len(valid_targets) >= 10:
            q25 = valid_targets.quantile(0.25)
            q75 = valid_targets.quantile(0.75)
            iqr = q75 - q25
            if iqr > 0:
                high_outliers = int((valid_targets > (q75 + 3.0 * iqr)).sum())
                if high_outliers > 0:
                    warnings.append(f"Detected {high_outliers} extreme demand spike(s) (> 3x IQR). Review for holiday promotions vs abnormal data errors.")

    # 5. Timestamp Conflict Detection (series_id + date duplicates)
    if date_col in df.columns and effective_series_series is not None and parsed_dates is not None:
        sub = pd.DataFrame({"series": effective_series_series, "date": parsed_dates})
        conflicting_records_count = int(sub.duplicated().sum())
        if conflicting_records_count > 0:
            errors.append(f"Detected {conflicting_records_count} conflicting record(s) where the same series has duplicate observations on the same timestamp.")

    # 6. Frequency Check Warning
    freq_label, freq_warn = detect_series_frequency(df, date_col, series_col if (series_col and series_col in df.columns) else "")
    if freq_warn:
        warnings.append(freq_warn)

    # 7. Series-Level Granular Validation
    series_quality_list: List[SeriesQualityItem] = []
    series_with_gaps = 0
    obs_counts: List[int] = []

    if effective_series_series is not None and date_col in df.columns and parsed_dates is not None:
        valid_mask = parsed_dates.notna() & effective_series_series.notna()
        work_df = pd.DataFrame({
            "series": effective_series_series.loc[valid_mask].astype(str),
            "date": parsed_dates.loc[valid_mask]
        })

        grouped = work_df.groupby("series")
        unique_series_names = list(grouped.groups.keys())

        # Sample up to 10 series for detailed representation
        sample_names = unique_series_names[:10]

        for s_name in unique_series_names:
            s_dates = grouped.get_group(s_name)["date"].sort_values()
            n_obs = len(s_dates)
            obs_counts.append(n_obs)

            if n_obs < 2:
                continue

            diffs = s_dates.diff().dt.total_seconds().div(86400).dropna()
            # If any gap is > 1.5 days for daily data
            has_gap = bool((diffs > 1.5).any())
            if has_gap:
                series_with_gaps += 1

            if s_name in sample_names:
                dup_dates = int(s_dates.duplicated().sum())
                span = int((s_dates.iloc[-1] - s_dates.iloc[0]).days) + 1
                missing_days = max(0, span - n_obs)

                series_quality_list.append(SeriesQualityItem(
                    series_id=s_name,
                    observation_count=n_obs,
                    start_date=s_dates.iloc[0].strftime("%Y-%m-%d"),
                    end_date=s_dates.iloc[-1].strftime("%Y-%m-%d"),
                    span_days=span,
                    missing_dates_count=missing_days,
                    duplicate_dates_count=dup_dates,
                    is_regular=not has_gap,
                ))

        if series_with_gaps > 0:
            warnings.append(f"{series_with_gaps} of {len(unique_series_names)} series contain temporal date gaps (> 1 day jump).")

        min_obs = int(min(obs_counts)) if obs_counts else 0
        med_obs = int(np.median(obs_counts)) if obs_counts else 0
        max_obs = int(max(obs_counts)) if obs_counts else 0

        if min_obs < 28 and min_obs > 0:
            warnings.append(f"Shortest series has only {min_obs} observations. At least 28 daily observations are recommended for short-horizon backtesting.")
    else:
        min_obs, med_obs, max_obs = 0, 0, 0

    series_summary = SeriesSummary(
        total_series=len(obs_counts),
        series_with_gaps=series_with_gaps,
        min_observations=min_obs,
        median_observations=med_obs,
        max_observations=max_obs,
        sample_series_quality=series_quality_list,
    )

    # 8. Determine Overall Status
    if missing_mandatory or errors or invalid_dates_count > 0 or invalid_target_count > 0 or conflicting_records_count > 5:
        overall_status = ReadinessStatus.NEEDS_ATTENTION
        if missing_mandatory:
            overall_status = ReadinessStatus.INVALID
    elif warnings:
        overall_status = ReadinessStatus.READY
    else:
        overall_status = ReadinessStatus.READY

    report = ValidationReport(
        dataset_id=dataset_id,
        status=overall_status,
        errors=errors,
        warnings=warnings,
        missing_mandatory_fields=missing_mandatory,
        mapped_fields=ColumnMapping(
            date=date_col,
            series_id=series_col or (composite_keys[0] if composite_keys else "default_series"),
            target=target_col,
            composite_series_keys=composite_keys,
            candidate_entity_columns=mapping.get("candidate_entity_columns", []),
            optional=mapping.get("optional", {})
        ),
        exact_duplicate_rows=exact_duplicates_count,
        conflicting_series_date_records=conflicting_records_count,
        invalid_dates_count=invalid_dates_count,
        invalid_target_values_count=invalid_target_count,
        negative_target_values_count=negative_target_count,
    )

    return report, series_summary
