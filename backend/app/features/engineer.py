"""
Feature Engineering Engine for Multi-Horizon Forecasting
ForecastIQ Backend — Phase 3

Features:
- Calendar features: day, weekday, week, month, year, is_weekend
- Lag features: lag_1, lag_7, lag_14, lag_28 strictly computed chronologically per series_id without leakage
- Rolling statistics: rolling_mean_7, rolling_mean_28 computed per series_id
- Model-specific formatters for:
  - ARIMA / SARIMA: univariate regular series per series_id
  - Prophet: ds, y, plus known future covariates
  - LightGBM: tabular feature matrix with lags, rolling statistics, calendar, and static entity categories
  - DeepAR / TFT: Darts-ready long format with past & future covariates
"""
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np


def engineer_time_series_features(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    lag_list: Optional[List[int]] = None,
    rolling_windows: Optional[List[int]] = None,
) -> pd.DataFrame:
    """
    Generate comprehensive features without data leakage:
    1. Calendar / Temporal features (known advance)
    2. Autoregressive lags computed per series
    3. Rolling statistics computed per series
    """
    date_col = mapping.get("date", "date")
    series_col = mapping.get("series_id", "series_id")
    target_col = mapping.get("target", "target")

    if lag_list is None:
        lag_list = [1, 7, 14, 28]
    if rolling_windows is None:
        rolling_windows = [7, 28]

    # Create work dataframe sorted strictly chronologically per series
    work_df = df.copy()
    series_col = mapping.get("series_id") or "series_id"
    if series_col not in work_df.columns:
        work_df["series_id"] = "default_series"
        series_col = "series_id"
    work_df[date_col] = pd.to_datetime(work_df[date_col], errors="coerce")
    work_df = work_df.sort_values(by=[series_col, date_col]).reset_index(drop=True)

    # 1. Calendar Features (KNOWN_FUTURE)
    work_df["calendar_day"] = work_df[date_col].dt.day
    work_df["calendar_weekday"] = work_df[date_col].dt.weekday
    work_df["calendar_week"] = work_df[date_col].dt.isocalendar().week.astype(int)
    work_df["calendar_month"] = work_df[date_col].dt.month
    work_df["calendar_year"] = work_df[date_col].dt.year
    work_df["is_weekend"] = work_df["calendar_weekday"].isin([5, 6]).astype(int)

    # 2. Lag Features (HISTORICAL_ONLY, computed strictly per series)
    if target_col in work_df.columns:
        grouped = work_df.groupby(series_col)[target_col]
        for lag in lag_list:
            work_df[f"target_lag_{lag}"] = grouped.shift(lag)

        # 3. Rolling Statistics (HISTORICAL_ONLY, computed per series shifted by 1 to prevent current-step leakage)
        # Shift 1 ensures rolling mean does not include the observation at time t
        shifted_target = grouped.shift(1)
        for window in rolling_windows:
            work_df[f"rolling_mean_{window}"] = (
                work_df.groupby(series_col)[target_col]
                .transform(lambda s: s.shift(1).rolling(window=window, min_periods=1).mean())
            )
            work_df[f"rolling_std_{window}"] = (
                work_df.groupby(series_col)[target_col]
                .transform(lambda s: s.shift(1).rolling(window=window, min_periods=1).std().fillna(0.0))
            )

    return work_df


def prepare_arima_dataset(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    series_id_val: Optional[str] = None
) -> pd.DataFrame:
    """
    Format univariate regular time-series dataset for ARIMA / SARIMA.
    Returns: date, target for the selected or first series.
    """
    date_col = mapping.get("date", "date")
    series_col = mapping.get("series_id", "series_id")
    target_col = mapping.get("target", "target")

    work_df = df.copy()
    series_col = mapping.get("series_id") or "series_id"
    if series_col not in work_df.columns:
        work_df["series_id"] = "default_series"
        series_col = "series_id"
    if series_id_val:
        work_df = work_df[work_df[series_col].astype(str) == str(series_id_val)]
    else:
        first_series = work_df[series_col].iloc[0] if len(work_df) > 0 else ""
        work_df = work_df[work_df[series_col] == first_series]

    work_df[date_col] = pd.to_datetime(work_df[date_col], errors="coerce")
    work_df = work_df.sort_values(by=date_col)

    res = pd.DataFrame({
        "date": work_df[date_col],
        "target": pd.to_numeric(work_df[target_col], errors="coerce")
    }).dropna().reset_index(drop=True)

    return res


def prepare_prophet_dataset(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    series_id_val: Optional[str] = None
) -> pd.DataFrame:
    """
    Format standard Prophet dataset (ds, y) with optional known covariates.
    """
    date_col = mapping.get("date", "date")
    series_col = mapping.get("series_id", "series_id")
    target_col = mapping.get("target", "target")

    work_df = df.copy()
    series_col = mapping.get("series_id") or "series_id"
    if series_col not in work_df.columns:
        work_df["series_id"] = "default_series"
        series_col = "series_id"
    if series_id_val:
        work_df = work_df[work_df[series_col].astype(str) == str(series_id_val)]
    else:
        first_series = work_df[series_col].iloc[0] if len(work_df) > 0 else ""
        work_df = work_df[work_df[series_col] == first_series]

    work_df[date_col] = pd.to_datetime(work_df[date_col], errors="coerce")
    work_df = work_df.sort_values(by=date_col)

    prophet_df = pd.DataFrame({
        "ds": work_df[date_col],
        "y": pd.to_numeric(work_df[target_col], errors="coerce")
    })

    # Add known future / event covariates if present
    for col in work_df.columns:
        if col not in [date_col, series_col, target_col]:
            col_lower = str(col).lower()
            if any(k in col_lower for k in ["promo", "holiday", "event", "price"]):
                prophet_df[col] = work_df[col].values

    return prophet_df.dropna(subset=["ds", "y"]).reset_index(drop=True)


def prepare_lightgbm_dataset(
    df: pd.DataFrame,
    mapping: Dict[str, Any]
) -> pd.DataFrame:
    """
    Format tabular ML feature matrix for LightGBM regression,
    including lags, rolling statistics, calendar covariates, and category codes.
    """
    engineered = engineer_time_series_features(df, mapping)
    series_col = mapping.get("series_id", "series_id")
    
    # Categorical label encoding
    res_df = engineered.copy()
    for col in res_df.columns:
        if res_df[col].dtype == "object" and col != mapping.get("date"):
            res_df[f"{col}_code"] = res_df[col].astype("category").cat.codes

    return res_df


def prepare_darts_dataset(
    df: pd.DataFrame,
    mapping: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Package series metadata and arrays ready for Darts TimeSeries conversion
    (for DeepAR and Temporal Fusion Transformer TFT models).
    """
    date_col = mapping.get("date", "date")
    series_col = mapping.get("series_id", "series_id")
    target_col = mapping.get("target", "target")

    work_df = df.copy()
    series_col = mapping.get("series_id") or "series_id"
    if series_col not in work_df.columns:
        work_df["series_id"] = "default_series"
        series_col = "series_id"
    work_df[date_col] = pd.to_datetime(work_df[date_col], errors="coerce")
    work_df = work_df.sort_values(by=[series_col, date_col]).reset_index(drop=True)

    past_covariates_cols = [c for c in work_df.columns if "lag_" in c or "rolling_" in c]
    future_covariates_cols = [c for c in work_df.columns if "calendar_" in c or c == "is_weekend" or "holiday" in str(c).lower()]

    series_dict = {}
    for s_id, s_df in work_df.groupby(series_col):
        series_dict[str(s_id)] = {
            "date": s_df[date_col].dt.strftime("%Y-%m-%d").tolist(),
            "target": s_df[target_col].tolist(),
            "past_covariates": {c: s_df[c].fillna(0).tolist() for c in past_covariates_cols if c in s_df.columns},
            "future_covariates": {c: s_df[c].fillna(0).tolist() for c in future_covariates_cols if c in s_df.columns},
        }

    return {
        "time_col": date_col,
        "group_col": series_col,
        "target_col": target_col,
        "total_series": len(series_dict),
        "series": series_dict,
    }
