"""
Real Data Cleaning Engine, Series Quality Analyzer, and Chronological Splitter
ForecastIQ Backend — Phase 3
"""
from typing import Dict, Any, List, Tuple, Optional
import pandas as pd
import numpy as np
from .schema import (
    ReadinessReport,
    ReadinessStatus,
    ColumnMapping,
    HorizonReadiness,
    ModelReadiness,
    PipelineStatus,
    CleaningReport,
    ConflictResolutionReport,
    SeriesQualityMetrics,
    SeriesQualityAnalysisReport,
    SplitSet,
    SplitReport,
)
from .profiler import profile_dataset, detect_series_frequency
from .validator import validate_schema_and_series
from ..features.analyzer import analyze_features


# Global store for cleaned datasets and artifacts in Phase 3
CLEANED_DATASET_STORE: Dict[str, Dict[str, Any]] = {}


def clean_canonical_dataset(
    dataset_id: str,
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    additive_aggregation: bool = True,
    target_type: str = "additive",
    impute_optional_features: bool = True,
) -> Tuple[pd.DataFrame, CleaningReport]:
    """
    Real cleaning pipeline:
    1. Exact duplicate rows removal
    2. Conflicting (series_id, date) detection and deterministic aggregation
    3. Missing values audit & imputation for optional covariates (zero-preservation on target)
    4. Negative target inspection
    5. Date gaps detection
    6. Contextual vs abnormal outlier detection
    """
    notes: List[str] = []
    original_rows = len(df)
    
    date_col = mapping.get("date", "date")
    series_col = mapping.get("series_id") or "series_id"
    target_col = mapping.get("target", "target")
    composite_keys = mapping.get("composite_series_keys") or []

    # Work on a copy
    work_df = df.copy()

    # Step 0: Ensure internal series identification column exists
    if composite_keys and all(ck in work_df.columns for ck in composite_keys):
        series_col = "series_id"
        work_df[series_col] = work_df[composite_keys].astype(str).agg("__".join, axis=1)
        notes.append(f"Constructed composite internal series identifier from columns: {', '.join(composite_keys)}.")
    elif series_col not in work_df.columns or work_df[series_col].isna().all():
        series_col = "series_id"
        work_df[series_col] = "default_series"
        notes.append("Assigned verified single-series internal identifier 'default_series'.")

    # Step 1: Remove exact duplicate rows
    initial_len = len(work_df)
    work_df = work_df.drop_duplicates()
    exact_duplicates_removed = initial_len - len(work_df)
    if exact_duplicates_removed > 0:
        notes.append(f"Removed {exact_duplicates_removed} exact duplicate row(s).")

    # Step 2: Validate and filter unparseable/invalid dates
    invalid_date_rows_excluded = 0
    if date_col in work_df.columns:
        parsed_dates = pd.to_datetime(work_df[date_col], errors="coerce")
        invalid_mask = parsed_dates.isna()
        invalid_date_rows_excluded = int(invalid_mask.sum())
        if invalid_date_rows_excluded > 0:
            notes.append(f"Excluded {invalid_date_rows_excluded} observation(s) with unparseable or malformed dates.")
            work_df = work_df.loc[~invalid_mask].copy()
            parsed_dates = parsed_dates.loc[~invalid_mask]
        work_df[date_col] = parsed_dates

    # Step 3: Missing Target Audit and Zero Preservation (BEFORE any groupby or aggregation!)
    missing_targets_found = 0
    missing_targets_handled = "NONE"
    missing_target_rows_excluded = 0
    zero_targets_preserved = 0
    negative_targets_flagged = 0
    negative_series_affected: List[str] = []

    if target_col in work_df.columns:
        # Numeric coercion
        numeric_target = pd.to_numeric(work_df[target_col], errors="coerce")
        missing_targets_found = int(numeric_target.isna().sum())

        if missing_targets_found > 0:
            missing_targets_handled = "EXCLUDED_FROM_TRAINING"
            missing_target_rows_excluded = missing_targets_found
            notes.append(f"Excluded {missing_targets_found} missing/non-numeric target observation(s) from model training. Never converted to 0.")
            work_df = work_df.loc[numeric_target.notna()].copy()
            numeric_target = numeric_target.loc[numeric_target.notna()]

        work_df[target_col] = numeric_target

        # Count genuine raw zero observations (after removing invalid dates and missing targets, but BEFORE grouping)
        zero_targets_preserved = int((work_df[target_col] == 0).sum())
        if zero_targets_preserved > 0:
            notes.append(f"Preserved {zero_targets_preserved} true zero target observation(s) as valid demand occurrences.")

    # Step 4: Conflicting (series_id, date) resolution
    conflicts_detected = 0
    conflicts_resolved = 0
    conflicting_observation_groups_resolved = 0
    unresolved_conflicts = 0
    aggregation_rule = "NONE"

    if series_col in work_df.columns and date_col in work_df.columns:
        # Check duplicate keys
        dup_keys = work_df.duplicated(subset=[series_col, date_col], keep=False)
        conflicts_count = int(dup_keys.sum())

        if conflicts_count > 0:
            conflicts_detected = conflicts_count
            conflicting_groups_count = int(work_df[dup_keys].groupby([series_col, date_col]).ngroups)
            if additive_aggregation and target_type == "additive":
                aggregation_rule = "SUM(target) + FIRST/TRUE(covariates)"
                # Define aggregation dictionary
                agg_dict: Dict[str, Any] = {}
                for c in work_df.columns:
                    if c in [series_col, date_col]:
                        continue
                    elif c == target_col:
                        agg_dict[c] = "sum"
                    elif pd.api.types.is_bool_dtype(work_df[c]) or any(k in str(c).lower() for k in ["promo", "holiday"]):
                        agg_dict[c] = "max"
                    elif pd.api.types.is_numeric_dtype(work_df[c]):
                        agg_dict[c] = "mean" if "price" in str(c).lower() else "first"
                    else:
                        agg_dict[c] = "first"

                # Perform deterministic group by
                pre_group_len = len(work_df)
                work_df = work_df.groupby([series_col, date_col], as_index=False).agg(agg_dict)
                conflicts_resolved = pre_group_len - len(work_df)
                conflicting_observation_groups_resolved = conflicting_groups_count
                notes.append(f"Resolved {conflicting_groups_count} conflicting timestamp group(s) ({conflicts_resolved} redundant observations aggregated) using deterministic additive SUM.")
            else:
                aggregation_rule = "FLAG_FOR_REVIEW"
                unresolved_conflicts = conflicts_count
                notes.append(f"Detected {conflicts_count} non-additive conflicts flagged for review.")

    # Step 5: Negative targets audit (preserved and flagged for review)
    if target_col in work_df.columns:
        neg_mask = work_df[target_col] < 0
        negative_targets_flagged = int(neg_mask.sum())
        if negative_targets_flagged > 0 and series_col in work_df.columns:
            negative_series_affected = list(work_df.loc[neg_mask, series_col].astype(str).unique())
            notes.append(f"Flagged {negative_targets_flagged} negative target value(s) across series {negative_series_affected}. Preserved for review; eligible for model training.")

    # Step 6: Optional Features Imputation
    optional_imputations_count = 0
    if impute_optional_features:
        covariate_cols = [c for c in work_df.columns if c not in [date_col, series_col, target_col]]
        for col in covariate_cols:
            n_na = int(work_df[col].isna().sum())
            if n_na > 0:
                optional_imputations_count += n_na
                if pd.api.types.is_numeric_dtype(work_df[col]):
                    if any(k in str(col).lower() for k in ["promo", "holiday", "event", "is_"]):
                        work_df[col] = work_df[col].fillna(0)
                    else:
                        work_df[col] = work_df[col].ffill().bfill().fillna(0)
                else:
                    work_df[col] = work_df[col].fillna("Unknown")
        if optional_imputations_count > 0:
            notes.append(f"Deterministically imputed {optional_imputations_count} missing optional covariate value(s).")

    # Step 7: Date Gaps & Cadence
    gaps_detected_count = 0
    if series_col in work_df.columns and date_col in work_df.columns:
        work_df = work_df.sort_values(by=[series_col, date_col]).reset_index(drop=True)
        for _, s_df in work_df.groupby(series_col):
            if len(s_df) >= 2:
                diffs = s_df[date_col].diff().dt.total_seconds().div(86400).dropna()
                gaps_detected_count += int((diffs > 1.5).sum())

        if gaps_detected_count > 0:
            notes.append(f"Detected {gaps_detected_count} temporal date gap(s) exceeding 1 day across series.")

    # Step 8: Outlier Detection with Contextual Cross-Check
    outliers_contextual_count = 0
    outliers_abnormal_count = 0

    if target_col in work_df.columns and len(work_df) >= 10:
        q25 = float(work_df[target_col].quantile(0.25))
        q75 = float(work_df[target_col].quantile(0.75))
        iqr = q75 - q25
        if iqr > 0:
            upper_threshold = q75 + 3.0 * iqr
        else:
            mean_val = float(work_df[target_col].mean())
            std_val = float(work_df[target_col].std())
            upper_threshold = mean_val + 2.5 * std_val if std_val > 0 else float("inf")
        outlier_mask = work_df[target_col] > upper_threshold
        total_outliers = int(outlier_mask.sum())

        if total_outliers > 0:
            context_cols = [c for c in work_df.columns if any(k in str(c).lower() for k in ["holiday", "promo", "event", "discount"])]
            if context_cols:
                context_active = pd.Series(False, index=work_df.index)
                for cc in context_cols:
                    context_active = context_active | (work_df[cc].notna() & (work_df[cc] != 0) & (work_df[cc] != False) & (work_df[cc] != ""))
                
                contextual_mask = outlier_mask & context_active
                outliers_contextual_count = int(contextual_mask.sum())
                outliers_abnormal_count = total_outliers - outliers_contextual_count
            else:
                outliers_abnormal_count = total_outliers

            notes.append(f"Detected {total_outliers} demand spike(s): {outliers_contextual_count} explained by contextual promotional/holiday events, {outliers_abnormal_count} flagged as abnormal.")

    # Pipeline Status
    if unresolved_conflicts > 0 or missing_targets_found > (original_rows * 0.2):
        pipeline_status = PipelineStatus.NEEDS_ATTENTION
    else:
        pipeline_status = PipelineStatus.READY_FOR_MODEL_TRAINING

    cleaned_row_count = len(work_df)
    eligible_for_training_row_count = cleaned_row_count

    cleaning_report = CleaningReport(
        dataset_id=dataset_id,
        original_rows=original_rows,
        cleaned_rows=cleaned_row_count,
        exact_duplicates_removed=exact_duplicates_removed,
        conflicts_detected=conflicts_detected,
        conflicts_resolved=conflicts_resolved,
        unresolved_conflicts=unresolved_conflicts,
        aggregation_rule=aggregation_rule,
        missing_targets_found=missing_targets_found,
        missing_targets_handled=missing_targets_handled,
        zero_targets_preserved=zero_targets_preserved,
        negative_targets_flagged=negative_targets_flagged,
        negative_series_affected=negative_series_affected,
        optional_imputations_count=optional_imputations_count,
        gaps_detected_count=gaps_detected_count,
        outliers_contextual_count=outliers_contextual_count,
        outliers_abnormal_count=outliers_abnormal_count,
        pipeline_status=pipeline_status,
        summary_notes=notes,
        raw_row_count=original_rows,
        exact_duplicate_rows_removed=exact_duplicates_removed,
        invalid_date_rows_excluded=invalid_date_rows_excluded,
        conflicting_observation_groups_resolved=conflicting_observation_groups_resolved,
        missing_target_rows_excluded_or_imputed=missing_target_rows_excluded,
        cleaned_row_count=cleaned_row_count,
        eligible_for_training_row_count=eligible_for_training_row_count,
    )

    # Save to global cleaned store
    CLEANED_DATASET_STORE[dataset_id] = {
        "df": work_df,
        "report": cleaning_report,
        "mapping": mapping,
    }

    return work_df, cleaning_report


def analyze_series_quality(
    dataset_id: str,
    df: pd.DataFrame,
    mapping: Dict[str, Any]
) -> SeriesQualityAnalysisReport:
    """
    Compute rigorous per-series quality metrics:
    - observation count, date span, frequency
    - missing target, zero count, negative count
    - gaps count, outlier count
    - mean, std, min, median, max
    - horizon feasibility: 7D (>= 28 obs), 28D (>= 90 obs), 90D (>= 180 obs)
    """
    date_col = mapping.get("date", "date")
    series_col = mapping.get("series_id") or "series_id"
    target_col = mapping.get("target", "target")
    composite_keys = mapping.get("composite_series_keys") or []

    work_df = df.copy()
    if composite_keys and all(ck in work_df.columns for ck in composite_keys):
        series_col = "series_id"
        work_df[series_col] = work_df[composite_keys].astype(str).agg("__".join, axis=1)
    elif series_col not in work_df.columns:
        series_col = "series_id"
        work_df[series_col] = "default_series"

    if date_col not in work_df.columns:
        return SeriesQualityAnalysisReport(
            dataset_id=dataset_id,
            total_series=0,
            feasible_7d_count=0,
            feasible_28d_count=0,
            feasible_90d_count=0,
            all_series_metrics=[],
        )

    work_df = df.copy()
    work_df[date_col] = pd.to_datetime(work_df[date_col], errors="coerce")
    if target_col in work_df.columns:
        work_df[target_col] = pd.to_numeric(work_df[target_col], errors="coerce")

    # Global IQR for outlier tagging
    q25_g = float(work_df[target_col].quantile(0.25)) if target_col in work_df.columns else 0.0
    q75_g = float(work_df[target_col].quantile(0.75)) if target_col in work_df.columns else 0.0
    iqr_g = q75_g - q25_g
    outlier_thresh = (q75_g + 3.0 * iqr_g) if iqr_g > 0 else float("inf")

    series_metrics: List[SeriesQualityMetrics] = []
    feasible_7d = 0
    feasible_28d = 0
    feasible_90d = 0

    for s_id, s_df in work_df.groupby(series_col):
        s_id_str = str(s_id)
        s_sorted = s_df.sort_values(by=date_col)
        n_obs = len(s_sorted)

        start_str = s_sorted[date_col].iloc[0].strftime("%Y-%m-%d") if n_obs > 0 and pd.notna(s_sorted[date_col].iloc[0]) else "N/A"
        end_str = s_sorted[date_col].iloc[-1].strftime("%Y-%m-%d") if n_obs > 0 and pd.notna(s_sorted[date_col].iloc[-1]) else "N/A"
        
        span_days = 0
        if n_obs >= 2 and pd.notna(s_sorted[date_col].iloc[0]) and pd.notna(s_sorted[date_col].iloc[-1]):
            span_days = int((s_sorted[date_col].iloc[-1] - s_sorted[date_col].iloc[0]).days) + 1

        # Gaps
        gap_count = 0
        if n_obs >= 2:
            diffs = s_sorted[date_col].diff().dt.total_seconds().div(86400).dropna()
            gap_count = int((diffs > 1.5).sum())

        # Target stats
        missing_target = 0
        zero_count = 0
        neg_count = 0
        outlier_count = 0
        t_mean, t_std, t_min, t_med, t_max = None, None, None, None, None

        if target_col in s_sorted.columns:
            t_series = s_sorted[target_col]
            missing_target = int(t_series.isna().sum())
            valid_t = t_series.dropna()
            if len(valid_t) > 0:
                zero_count = int((valid_t == 0).sum())
                neg_count = int((valid_t < 0).sum())
                outlier_count = int((valid_t > outlier_thresh).sum())
                t_mean = round(float(valid_t.mean()), 2)
                t_std = round(float(valid_t.std()), 2) if len(valid_t) > 1 else 0.0
                t_min = round(float(valid_t.min()), 2)
                t_med = round(float(valid_t.median()), 2)
                t_max = round(float(valid_t.max()), 2)

        dup_count = int(s_sorted.duplicated(subset=[date_col]).sum())

        # Horizon feasibility thresholds
        h7_ok = n_obs >= 28
        h28_ok = n_obs >= 90
        h90_ok = n_obs >= 180

        if h7_ok:
            feasible_7d += 1
        if h28_ok:
            feasible_28d += 1
        if h90_ok:
            feasible_90d += 1

        status_str = "READY" if h7_ok else "LIMITED"
        note_str = "Supported for multi-horizon models" if h28_ok else ("Short-term only (<90 obs)" if h7_ok else "Insufficient history (<28 obs)")

        series_metrics.append(SeriesQualityMetrics(
            series_id=s_id_str,
            observation_count=n_obs,
            start_date=start_str,
            end_date=end_str,
            span_days=span_days,
            frequency="Daily" if gap_count == 0 else "Irregular",
            missing_target_count=missing_target,
            duplicate_count=dup_count,
            conflict_count=dup_count,
            gap_count=gap_count,
            zero_count=zero_count,
            negative_count=neg_count,
            outlier_count=outlier_count,
            target_mean=t_mean,
            target_std=t_std,
            target_min=t_min,
            target_median=t_med,
            target_max=t_max,
            horizon_7d_feasible=h7_ok,
            horizon_28d_feasible=h28_ok,
            horizon_90d_feasible=h90_ok,
            status=status_str,
            note=note_str,
        ))

    return SeriesQualityAnalysisReport(
        dataset_id=dataset_id,
        total_series=len(series_metrics),
        feasible_7d_count=feasible_7d,
        feasible_28d_count=feasible_28d,
        feasible_90d_count=feasible_90d,
        all_series_metrics=series_metrics,
    )


def split_series_chronological_80_20(
    series_df: pd.DataFrame,
    time_col: str = "date",
    train_ratio: float = 0.8,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split a single series chronologically into train (earliest 80%) and test (latest 20%).
    
    Rounding policy:
    - n_train = int(np.round(total_obs * train_ratio))
    - When not divisible by 5 (e.g. 101 obs): round(101 * 0.8) = round(80.8) = 81 train, 20 test.
    - Guarantees: n_train >= 1 and n_test >= 1 for any series with total_obs >= 2.
    - Never random shuffles.
    - Preserves temporal order: all train dates precede all test dates.
    """
    sorted_df = series_df.sort_values(by=time_col).reset_index(drop=True)
    total_obs = len(sorted_df)
    if total_obs == 0:
        return sorted_df.copy(), sorted_df.copy()
    if total_obs == 1:
        return sorted_df.copy(), sorted_df.iloc[0:0].copy()

    n_train = int(np.round(total_obs * train_ratio))
    n_train = max(1, min(n_train, total_obs - 1))
    train_df = sorted_df.iloc[:n_train].copy().reset_index(drop=True)
    test_df = sorted_df.iloc[n_train:].copy().reset_index(drop=True)
    return train_df, test_df


def split_dataset_chronological_80_20(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    train_ratio: float = 0.8,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Universal Chronological 80:20 Train-Test Split for single-series and multi-series datasets.
    
    Multi-series policy:
    - Splits each distinct series chronologically by its own temporal timestamps.
    - Preserves each series' temporal continuity and ordering without inter-series leakage.
    - Recombines into overall train_df and test_df while maintaining series identities.
    - Missing series_id is handled via Phase 1 internal resolution ('default_series' or composite keys).
    """
    time_col = mapping.get("date", "date")
    series_col = mapping.get("series_id", "series_id")
    composite_keys = mapping.get("composite_series_keys") or []

    work_df = df.copy()
    work_df[time_col] = pd.to_datetime(work_df[time_col], errors="coerce")
    work_df = work_df.dropna(subset=[time_col])

    # Ensure internal series_id is populated if missing
    if composite_keys and all(ck in work_df.columns for ck in composite_keys) and series_col not in work_df.columns:
        work_df["series_id"] = work_df[composite_keys].astype(str).agg("__".join, axis=1)
        series_col = "series_id"
    elif series_col not in work_df.columns:
        work_df["series_id"] = "default_series"
        series_col = "series_id"

    train_parts = []
    test_parts = []

    for _, s_group in work_df.groupby(series_col, sort=False):
        tr, te = split_series_chronological_80_20(s_group, time_col=time_col, train_ratio=train_ratio)
        train_parts.append(tr)
        test_parts.append(te)

    train_df = pd.concat(train_parts, ignore_index=True) if train_parts else work_df.iloc[0:0].copy()
    test_df = pd.concat(test_parts, ignore_index=True) if test_parts else work_df.iloc[0:0].copy()

    return train_df, test_df


def compute_chronological_splits(
    dataset_id: str,
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    test_horizon_days: Optional[int] = None,
    val_horizon_days: Optional[int] = None,
    use_80_20_ratio: bool = True,
) -> SplitReport:
    """
    Universal Time-Based Chronological Split:
    Default: Universal 80:20 train-test split policy.
    Earliest 80% of observations for training; latest 20% for testing.
    Never random shuffle. Strictly preserves temporal order per series.
    Also supports explicit test_horizon_days / val_horizon_days when requested by legacy callers.
    """
    date_col = mapping.get("date", "date")
    series_col = mapping.get("series_id", "series_id")
    composite_keys = mapping.get("composite_series_keys") or []

    work_df = df.copy()
    work_df[date_col] = pd.to_datetime(work_df[date_col], errors="coerce")
    work_df = work_df.dropna(subset=[date_col]).sort_values(by=date_col)

    if composite_keys and all(ck in work_df.columns for ck in composite_keys) and series_col not in work_df.columns:
        work_df["series_id"] = work_df[composite_keys].astype(str).agg("__".join, axis=1)
        series_col = "series_id"
    elif series_col not in work_df.columns:
        work_df["series_id"] = "default_series"
        series_col = "series_id"

    all_dates = pd.Series(work_df[date_col].unique()).sort_values().reset_index(drop=True)
    total_dates = len(all_dates)

    # If caller specifically passed explicit horizons (e.g. test_horizon=28, val_horizon=14)
    # AND strategy is not explicitly "80:20" or use_80_20_ratio was not explicitly set to True without horizons:
    is_explicit_fixed_horizons = (
        test_horizon_days is not None
        and val_horizon_days is not None
    )

    if is_explicit_fixed_horizons:
        if total_dates < (test_horizon_days + val_horizon_days + 7):
            test_days = max(1, int(total_dates * 0.15))
            val_days = max(1, int(total_dates * 0.15))
        else:
            test_days = test_horizon_days
            val_days = val_horizon_days

        test_start_idx = total_dates - test_days
        val_start_idx = test_start_idx - val_days

        train_dates = all_dates.iloc[:val_start_idx]
        val_dates = all_dates.iloc[val_start_idx:test_start_idx]
        test_dates = all_dates.iloc[test_start_idx:]

        train_df = work_df[work_df[date_col].isin(train_dates)]
        val_df = work_df[work_df[date_col].isin(val_dates)]
        test_df = work_df[work_df[date_col].isin(test_dates)]
        strategy_desc = "Strict Chronological Cutoff (Train -> Validation -> Test)"
        split_ratio_label = "Custom Fixed Horizon"
    else:
        # Standard Universal 80:20 chronological split
        train_df, test_df = split_dataset_chronological_80_20(work_df, mapping=mapping, train_ratio=0.8)
        # Validation subset within training period for hyperparameter tuning / sanity check
        val_df = pd.DataFrame(columns=work_df.columns)
        if len(train_df) >= 10:
            # Carve inner 10% of training set for validation without touching test set
            val_df, _ = split_dataset_chronological_80_20(train_df, mapping=mapping, train_ratio=0.9)
            val_df = train_df.iloc[len(val_df):].copy()

        train_dates = pd.Series(train_df[date_col].unique()).sort_values().reset_index(drop=True)
        val_dates = pd.Series(val_df[date_col].unique()).sort_values().reset_index(drop=True) if len(val_df) > 0 else pd.Series(dtype="datetime64[ns]")
        test_dates = pd.Series(test_df[date_col].unique()).sort_values().reset_index(drop=True)

        test_days = len(test_dates)
        val_days = len(val_dates)
        strategy_desc = "Universal 80:20 Chronological Split (Train: 80%, Test: 20%)"
        split_ratio_label = "80:20"

    def fmt_date(dt_series):
        if len(dt_series) == 0:
            return "N/A", "N/A"
        return dt_series.iloc[0].strftime("%Y-%m-%d"), dt_series.iloc[-1].strftime("%Y-%m-%d")

    tr_start, tr_end = fmt_date(train_dates)
    va_start, va_end = fmt_date(val_dates)
    te_start, te_end = fmt_date(test_dates)

    n_series = int(work_df[series_col].nunique()) if series_col in work_df.columns else 1

    return SplitReport(
        dataset_id=dataset_id,
        train=SplitSet(
            name="Train Set",
            start_date=tr_start,
            end_date=tr_end,
            rows_count=len(train_df),
            series_count=int(train_df[series_col].nunique()) if series_col in train_df.columns else n_series,
        ),
        val=SplitSet(
            name="Validation Set",
            start_date=va_start,
            end_date=va_end,
            rows_count=len(val_df),
            series_count=int(val_df[series_col].nunique()) if series_col in val_df.columns else n_series,
        ),
        test=SplitSet(
            name="Test Set",
            start_date=te_start,
            end_date=te_end,
            rows_count=len(test_df),
            series_count=int(test_df[series_col].nunique()) if series_col in test_df.columns else n_series,
        ),
        split_strategy=strategy_desc,
        test_horizon_days=test_days,
        val_horizon_days=val_days,
        train_row_count=len(train_df),
        validation_row_count=len(val_df),
        test_row_count=len(test_df),
        split_ratio=split_ratio_label,
        train_pct=round(len(train_df) / max(1, len(work_df)) * 100, 1),
        test_pct=round(len(test_df) / max(1, len(work_df)) * 100, 1),
    )


def evaluate_dataset_readiness(
    dataset_id: str,
    df: pd.DataFrame,
    filename: str,
    custom_mapping: Dict[str, Any]
) -> ReadinessReport:
    """
    Run full multi-layer evaluation:
    1. Schema & Series Validation
    2. Statistical Dataset Profiling
    3. Feature Analysis & Classification
    4. Multi-Horizon Feasibility & Model Compatibility
    """
    # 1. Validation Report
    val_report, series_summary = validate_schema_and_series(dataset_id, df, custom_mapping)

    # 2. Profile
    profile = profile_dataset(dataset_id, df, filename, custom_mapping)

    # 3. Features
    features = analyze_features(df, custom_mapping)

    # 4. Multi-Horizon Feasibility
    span_days = profile.date_range.total_days
    horizons = {
        "h7": HorizonReadiness(
            days=7,
            label="7 Days (Short-term)",
            status="Supported" if span_days >= 28 else "Limited Data",
            note="Sufficient historical observations for operational replenishment lag features." if span_days >= 28 else "Requires at least 28 days of history."
        ),
        "h28": HorizonReadiness(
            days=28,
            label="28 Days (Medium-term)",
            status="Supported" if span_days >= 90 else ("Borderline" if span_days >= 45 else "Insufficient"),
            note="Full monthly cycle coverage with rolling window statistics support." if span_days >= 90 else "Requires at least 90 days for monthly seasonal cycles."
        ),
        "h90": HorizonReadiness(
            days=90,
            label="90 Days (Long-term)",
            status="Supported" if span_days >= 180 else "Limited",
            note="Quarterly planning supported across deep multi-horizon models." if span_days >= 180 else "Requires at least 180+ days for reliable 90-day training."
        )
    }

    # 5. Model Architecture Compatibility
    unique_series = profile.unique_series_count
    models = [
        ModelReadiness(
            model="ARIMA / SARIMA",
            type="Statistical Baseline",
            ready=unique_series > 0 and span_days >= 30 and val_report.status != ReadinessStatus.INVALID,
            requirement="Univariate regular chronological series per entity."
        ),
        ModelReadiness(
            model="Prophet",
            type="Additive Seasonality",
            ready=span_days >= 60 and val_report.status != ReadinessStatus.INVALID,
            requirement="Supports trend changes, day-of-week cycles, and holiday regressors."
        ),
        ModelReadiness(
            model="LightGBM",
            type="Tabular Machine Learning",
            ready=span_days >= 45 and val_report.status != ReadinessStatus.INVALID,
            requirement="Engineers lag 1/7/14/28, rolling stats, and categorical hierarchical features."
        ),
        ModelReadiness(
            model="DeepAR",
            type="Deep Learning (RNN)",
            ready=unique_series >= 1 and span_days >= 60 and val_report.status != ReadinessStatus.INVALID,
            requirement="Probabilistic autoregressive RNN training across related series."
        ),
        ModelReadiness(
            model="Temporal Fusion Transformer (TFT)",
            type="Deep Multi-Horizon Attention",
            ready=span_days >= 90 and val_report.status != ReadinessStatus.INVALID,
            requirement="Self-attention architecture processing static covariates and time-varying inputs."
        )
    ]

    # Pre-flight Checklist
    checklist = [
        {
            "title": "Mandatory Columns Mapped",
            "passed": len(val_report.missing_mandatory_fields) == 0,
            "detail": f"date='{custom_mapping.get('date', '')}', series_id='{custom_mapping.get('series_id', '')}', target='{custom_mapping.get('target', '')}'" if len(val_report.missing_mandatory_fields) == 0 else f"Missing: {', '.join(val_report.missing_mandatory_fields)}"
        },
        {
            "title": "Valid Chronological Range",
            "passed": val_report.invalid_dates_count == 0 and span_days > 0,
            "detail": f"{profile.date_range.start_date} to {profile.date_range.end_date} ({span_days} days, {profile.detected_frequency})"
        },
        {
            "title": "Target Numerical Validity",
            "passed": val_report.invalid_target_values_count == 0 and bool(custom_mapping.get("target", "")),
            "detail": f"{profile.target_statistics.count} numerically parseable raw observation(s) ({profile.target_statistics.zero_count} zero sales, {val_report.negative_target_values_count} negative entries flagged for review; non-numeric/missing targets excluded prior to training)"
        },
        {
            "title": "Series Entity Keys Identified",
            "passed": unique_series > 0,
            "detail": f"{unique_series} unique series identified"
        },
        {
            "title": "Timestamp Uniqueness per Series",
            "passed": val_report.conflicting_series_date_records == 0,
            "detail": "No duplicate timestamps within series" if val_report.conflicting_series_date_records == 0 else f"{val_report.conflicting_series_date_records} duplicate timestamp(s) found"
        }
    ]

    return ReadinessReport(
        dataset_id=dataset_id,
        filename=filename,
        status=val_report.status,
        errors=val_report.errors,
        warnings=val_report.warnings,
        profile=profile,
        column_mapping=val_report.mapped_fields,
        feature_classifications=features,
        series_summary=series_summary,
        readiness_checklist=checklist,
        supported_horizons=horizons,
        model_compatibility=models,
    )
