"""
Feature Analyzer Module
ForecastIQ Backend
"""
from typing import Dict, Any, List
import pandas as pd
from ..data.schema import ColumnFeatureProfile, ColumnClassification


def analyze_features(
    df: pd.DataFrame,
    mapping: Dict[str, Any]
) -> List[ColumnFeatureProfile]:
    """
    Examine every column in the dataset, calculate statistics,
    and classify each for multi-horizon model eligibility.
    """
    date_col = mapping.get("date", "")
    series_col = mapping.get("series_id", "")
    target_col = mapping.get("target", "")

    total_rows = max(1, len(df))
    feature_profiles: List[ColumnFeatureProfile] = []

    for col in df.columns:
        col_series = df[col]
        dtype_str = str(col_series.dtype)
        nunique = int(col_series.nunique(dropna=True))
        missing_count = int(col_series.isna().sum())
        missing_pct = round(float((missing_count / total_rows) * 100), 2)
        sample_vals = [str(x) for x in col_series.dropna().head(3).tolist()]

        col_lower = str(col).lower().strip()

        # 1. Primary Mapping Roles
        if col == date_col:
            classification = ColumnClassification.TIME
            reason = "Designated mandatory temporal index for sequencing observations."
        elif col == target_col:
            classification = ColumnClassification.TARGET
            reason = "Designated mandatory numerical target quantity for forecasting."
        elif col == series_col:
            classification = ColumnClassification.SERIES_ID
            reason = "Designated mandatory entity grouping key for individual time series."

        # 2. Check for Constant columns
        elif nunique <= 1:
            classification = ColumnClassification.CONSTANT
            reason = "Single constant value across all rows; zero variance, excluded from model training."

        # 3. Check for Future Provided (user-uploaded future covariate planned ahead)
        elif any(f_prov in col_lower for f_prov in ["future_provided", "planned_promo", "planned_discount", "planned_event"]):
            classification = ColumnClassification.FUTURE_PROVIDED
            reason = "Future covariate provided ahead of time by business planning for forecast horizons."

        # 4. Check for Potential Data Leakage
        elif any(leak in col_lower for leak in ["leakage", "future", "actual_future", "next_day", "tomorrow", "subsequent", "target_future"]):
            classification = ColumnClassification.POTENTIAL_LEAKAGE
            reason = "Name suggests data from future time periods; risks severe target leakage."
        elif any(pred in col_lower for pred in ["prediction", "model_forecast", "external_pred"]):
            classification = ColumnClassification.POTENTIAL_LEAKAGE
            reason = "Appears to be a model output from an external system rather than an input covariate."

        # 5. Check for Historical Only Covariates (e.g. foot traffic, measured weather, historical returns)
        elif any(hist in col_lower for hist in ["traffic", "footfall", "foot_traffic", "weather_actual", "measured_temp", "returns", "stockout", "historical_only"]):
            classification = ColumnClassification.HISTORICAL_ONLY
            reason = "Only observable historically; unavailable into the future without external forecast assumptions."

        # 6. Check for Calendar / Known Future Covariates (e.g. holidays, day of week, events)
        elif any(cal in col_lower for cal in ["holiday", "event", "is_holiday", "easter", "christmas", "superbowl"]):
            classification = ColumnClassification.KNOWN_FUTURE
            reason = "Calendar event/holiday known in advance for both past and future forecast horizons."
        elif any(cal in col_lower for cal in ["weekday", "month", "year", "quarter", "day_of_week", "dayofweek", "day_of_month", "is_weekend"]):
            classification = ColumnClassification.KNOWN_FUTURE
            reason = "Deterministic astronomical/calendar covariate known ahead of time across all horizons."

        # 7. Check for Price / Marketing Covariates
        elif any(econ in col_lower for econ in ["price", "sell_price", "discount", "promo", "promotion", "coupon"]):
            classification = ColumnClassification.POTENTIALLY_USEFUL
            reason = "Economic/marketing covariate; can serve as historical feature or planned future promotional input."

        # 8. Check for Location / Hierarchy Static Metadata
        elif any(hier in col_lower for hier in ["store", "branch", "warehouse", "category", "dept", "state", "region"]):
            classification = ColumnClassification.CATEGORICAL
            reason = "Hierarchical entity metadata; ideal for multi-series embeddings in LightGBM, DeepAR, and TFT."

        # 9. Check for High-Cardinality Free Text / Identifiers
        elif (nunique > (total_rows * 0.9) and not pd.api.types.is_numeric_dtype(col_series)) or any(ident in col_lower for ident in ["transaction_id", "row_id", "order_id"]):
            classification = ColumnClassification.IDENTIFIER
            reason = "High-cardinality row/transaction identifier; not suitable as standard categorical feature."

        # 10. Standard Numerical
        elif pd.api.types.is_numeric_dtype(col_series):
            classification = ColumnClassification.NUMERICAL
            reason = "Continuous numeric feature; suitable for lag, rolling window statistics, and normalization."

        # 11. General Categorical
        else:
            classification = ColumnClassification.CATEGORICAL
            reason = "Discrete categorical column; suitable for label or one-hot encoding."

        feature_profiles.append(ColumnFeatureProfile(
            name=str(col),
            data_type=dtype_str,
            unique_count=nunique,
            missing_count=missing_count,
            missing_percentage=missing_pct,
            classification=classification,
            reason=reason,
            sample_values=sample_vals,
        ))

    return feature_profiles

