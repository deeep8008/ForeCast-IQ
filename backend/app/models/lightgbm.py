"""
LightGBM Multi-Step Recursive Forecasting Model Implementation (Phase 5)
ForecastIQ Backend

Forecasting Strategy:
- Supervised Tabular Regression with LightGBM (LGBMRegressor)
- Recursive Multi-Step Forecasting for 7, 28, and 90-day horizons:
  1. Train a LightGBM regressor on engineered historical features:
     - Autoregressive Lags: lag_1, lag_7, lag_14, lag_28 (computed chronologically per series)
     - Rolling Window Statistics: rolling_mean_7, rolling_mean_28, rolling_std_7, rolling_std_28 (shifted by 1 to prevent current-step target leakage)
     - Calendar Covariates (known ahead): calendar_day, calendar_weekday, calendar_week, calendar_month, calendar_year, is_weekend
     - Validated static/hierarchical categories (label encoded)
  2. For out-of-sample forecasting:
     - Advance day-by-day recursively across the forecast horizon.
     - Recompute autoregressive lags (lag_1, lag_7, lag_14, lag_28) using previous predictions as the forecast rolls forward.
     - Recompute rolling statistics over the composite sequence (history + prior predictions).
     - NEVER use actual future test targets as features.
- Output: Standardized ForecastResult with null/empty lower and upper bounds
  (LightGBM does not inherently produce statistical parametric confidence intervals; no fake uncertainty is fabricated).
"""
import time
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
import lightgbm as lgb
from .base import BaseForecaster
from .config import ModelDefaults
from ..features.engineer import engineer_time_series_features
from ..data.schema import ForecastResult, ForecastPoint


class LightgbmForecaster(BaseForecaster):
    """
    Tabular Gradient Boosted Decision Tree Forecaster using LightGBM.
    Supports recursive multi-step forecasting across 7D, 28D, and 90D horizons.
    """
    def __init__(
        self,
        n_estimators: Optional[int] = None,
        learning_rate: Optional[float] = None,
        num_leaves: Optional[int] = None,
        max_depth: Optional[int] = None,
        subsample: Optional[float] = None,
        random_state: Optional[int] = None,
    ):
        super().__init__(
            model_name="LightGBM",
            model_type="Tabular Gradient Boosting",
            supported_horizons=[7, 28, 90]
        )
        self.n_estimators = n_estimators if n_estimators is not None else ModelDefaults.LGBM_N_ESTIMATORS
        self.learning_rate = learning_rate if learning_rate is not None else ModelDefaults.LGBM_LEARNING_RATE
        self.num_leaves = num_leaves if num_leaves is not None else ModelDefaults.LGBM_NUM_LEAVES
        self.max_depth = max_depth if max_depth is not None else ModelDefaults.LGBM_MAX_DEPTH
        self.subsample = subsample if subsample is not None else ModelDefaults.LGBM_SUBSAMPLE
        self.random_state = random_state if random_state is not None else ModelDefaults.LGBM_RANDOM_STATE

        self.model: Optional[lgb.LGBMRegressor] = None
        self.feature_columns: List[str] = []
        self.training_df: Optional[pd.DataFrame] = None
        self.time_col: str = "date"
        self.target_col: str = "target"
        self.series_col: str = "series_id"
        self.category_encoders: Dict[str, Dict[str, int]] = {}

    def _prepare_tabular_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate calendar, lag, and rolling features using existing feature engine,
        and encode non-numeric covariates cleanly.
        """
        mapping = {
            "date": self.time_col,
            "series_id": self.series_col,
            "target": self.target_col
        }
        feat_df = engineer_time_series_features(
            df=df,
            mapping=mapping,
            lag_list=[1, 7, 14, 28],
            rolling_windows=[7, 28]
        )

        # Drop the series_id as a predictor feature to prevent meaningless numeric coding
        # Handle optional categorical/string columns safely with label encoding
        for col in feat_df.columns:
            if col in [self.time_col, self.series_col, self.target_col]:
                continue
            if not pd.api.types.is_numeric_dtype(feat_df[col]):
                if col not in self.category_encoders:
                    unique_vals = sorted(feat_df[col].dropna().astype(str).unique())
                    self.category_encoders[col] = {v: i for i, v in enumerate(unique_vals)}
                mapping_dict = self.category_encoders[col]
                feat_df[col] = feat_df[col].astype(str).map(mapping_dict).fillna(-1).astype(float)

        return feat_df

    def fit(
        self,
        df: pd.DataFrame,
        time_col: str,
        target_col: str,
        horizon: int = 28,
        series_col: str = "series_id",
        **kwargs
    ) -> "LightgbmForecaster":
        """
        Validate single-series data, engineer features chronologically,
        and fit LightGBM regressor on historical observation rows.
        """
        self.validate_series_data(df, time_col, target_col, horizon)

        work_df = df.copy()
        work_df[time_col] = pd.to_datetime(work_df[time_col])
        work_df = work_df.sort_values(by=time_col).reset_index(drop=True)

        self.time_col = time_col
        self.target_col = target_col
        self.series_col = series_col if series_col in work_df.columns else "series_id"
        if self.series_col not in work_df.columns:
            work_df[self.series_col] = "SERIES_1"

        self.training_df = work_df

        # Generate tabular features
        tabular_df = self._prepare_tabular_features(work_df)

        # Drop rows with NaN lag/rolling features caused by initial lookback window (e.g. first 28 rows)
        feature_cols = [
            c for c in tabular_df.columns 
            if c not in [self.time_col, self.series_col, self.target_col]
        ]
        self.feature_columns = feature_cols

        # Clean training slice
        train_data = tabular_df.dropna(subset=self.feature_columns + [self.target_col]).reset_index(drop=True)
        if len(train_data) < 5:
            # Fallback to smaller lags if series is short
            raise ValueError(
                f"Series history ({len(work_df)} obs) is insufficient after applying 28-day lag features. "
                f"At least 35 observations are required to train LightGBM."
            )

        X_train = train_data[self.feature_columns]
        y_train = train_data[self.target_col].astype(float)

        self.model = lgb.LGBMRegressor(
            n_estimators=self.n_estimators,
            learning_rate=self.learning_rate,
            num_leaves=self.num_leaves,
            max_depth=self.max_depth,
            subsample=self.subsample,
            random_state=self.random_state,
            verbose=-1,
        )

        try:
            self.model.fit(X_train, y_train)
            self.is_fitted = True
            self.metadata = {
                "n_estimators": self.n_estimators,
                "learning_rate": self.learning_rate,
                "num_leaves": self.num_leaves,
                "feature_count": len(self.feature_columns),
                "features_used": self.feature_columns,
                "n_training_rows": len(train_data),
            }
        except Exception as e:
            raise RuntimeError(f"Failed to fit LightGBM model: {str(e)}")

        return self

    def forecast(
        self,
        horizon: int,
        dataset_id: str,
        series_id: str,
        **kwargs
    ) -> ForecastResult:
        """
        Execute recursive multi-step forecasting:
        - Advance day-by-day across horizon.
        - Compute feature vector for day t using historical observations and previously predicted values.
        - Predict target value for day t and append to forecast series.
        - No test targets or future actual values are ever accessed.
        """
        if not self.is_fitted or self.model is None or self.training_df is None:
            raise RuntimeError("Model must be fitted before generating forecast.")

        start_time = time.time()
        last_date = self.training_df[self.time_col].iloc[-1]
        future_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=horizon, freq="D")
        date_strs = [d.strftime("%Y-%m-%d") for d in future_dates]

        # Working sequence: copy of historical dates and targets
        hist_dates = list(self.training_df[self.time_col].values)
        hist_targets = list(self.training_df[self.target_col].astype(float).values)

        forecast_values: List[float] = []

        # Recursive prediction loop
        for step_idx, future_dt in enumerate(future_dates):
            # 1. Calendar features for future_dt
            cal_day = future_dt.day
            cal_weekday = future_dt.weekday()
            cal_week = future_dt.isocalendar().week
            cal_month = future_dt.month
            cal_year = future_dt.year
            is_weekend = int(cal_weekday in [5, 6])

            # 2. Lag features computed from hist_targets (which grows with predictions)
            lag_1 = hist_targets[-1]
            lag_7 = hist_targets[-7] if len(hist_targets) >= 7 else hist_targets[0]
            lag_14 = hist_targets[-14] if len(hist_targets) >= 14 else hist_targets[0]
            lag_28 = hist_targets[-28] if len(hist_targets) >= 28 else hist_targets[0]

            # 3. Rolling window statistics (shifted by 1 -> over the sequence prior to future_dt)
            roll_7_window = hist_targets[-7:]
            roll_28_window = hist_targets[-28:] if len(hist_targets) >= 28 else hist_targets

            roll_mean_7 = float(np.mean(roll_7_window))
            roll_std_7 = float(np.std(roll_7_window)) if len(roll_7_window) > 1 else 0.0
            roll_mean_28 = float(np.mean(roll_28_window))
            roll_std_28 = float(np.std(roll_28_window)) if len(roll_28_window) > 1 else 0.0

            # Construct feature row dictionary matching self.feature_columns
            row_dict: Dict[str, Any] = {
                "calendar_day": cal_day,
                "calendar_weekday": cal_weekday,
                "calendar_week": cal_week,
                "calendar_month": cal_month,
                "calendar_year": cal_year,
                "is_weekend": is_weekend,
                "target_lag_1": lag_1,
                "target_lag_7": lag_7,
                "target_lag_14": lag_14,
                "target_lag_28": lag_28,
                "rolling_mean_7": roll_mean_7,
                "rolling_std_7": roll_std_7,
                "rolling_mean_28": roll_mean_28,
                "rolling_std_28": roll_std_28,
            }

            # Optional static/covariate columns
            for col in self.feature_columns:
                if col not in row_dict:
                    # Static/covariate values retain their last observed historical value
                    if col in self.training_df.columns:
                        last_val = self.training_df[col].iloc[-1]
                        if col in self.category_encoders:
                            row_dict[col] = self.category_encoders[col].get(str(last_val), -1)
                        else:
                            row_dict[col] = last_val
                    else:
                        row_dict[col] = 0.0

            # Ensure row features are aligned in the exact column order expected by the model
            step_features = pd.DataFrame([row_dict])[self.feature_columns]

            # Predict 1 step ahead
            pred_step = float(self.model.predict(step_features)[0])
            pred_step_clipped = round(max(0.0, pred_step), 2)

            forecast_values.append(pred_step_clipped)

            # Append to recursive state
            hist_dates.append(pd.to_datetime(future_dt))
            hist_targets.append(pred_step_clipped)

        # Confidence intervals: LightGBM does not inherently produce parametric prediction intervals.
        # Strict rule: DO NOT fabricate confidence intervals. Return None / empty.
        lower_bound = None
        upper_bound = None

        points = [
            ForecastPoint(
                date=d_str,
                forecast=f_val,
                lower_bound=None,
                upper_bound=None
            )
            for d_str, f_val in zip(date_strs, forecast_values)
        ]

        exec_time = round((time.time() - start_time) * 1000, 2)
        train_start_str = self.training_df[self.time_col].iloc[0].strftime("%Y-%m-%d")
        train_end_str = last_date.strftime("%Y-%m-%d")

        return ForecastResult(
            dataset_id=dataset_id,
            series_id=series_id,
            model="LightGBM",
            forecast_horizon=horizon,
            dates=date_strs,
            forecast=forecast_values,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            points=points,
            components={
                "forecasting_strategy": "Recursive Multi-Step Autoregressive Tabular Regression",
                "n_features": len(self.feature_columns),
                "feature_names": self.feature_columns,
                "n_estimators": self.n_estimators,
                "learning_rate": self.learning_rate,
                "uncertainty_note": "LightGBM does not produce statistical parametric intervals; intervals are not fabricated."
            },
            training_start=train_start_str,
            training_end=train_end_str,
            forecast_start=date_strs[0],
            forecast_end=date_strs[-1],
            execution_time_ms=exec_time,
            status="SUCCESS",
            notes=[
                f"Fitted LightGBM on {len(self.training_df)} observations using {len(self.feature_columns)} features.",
                f"Generated {horizon}-day recursive out-of-sample forecast without future target leakage."
            ]
        )
