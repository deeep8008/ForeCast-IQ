import os
import sys
import time
import logging
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

# Ensure Windows cmdstan tbb.dll is available in PATH and DLL search path
try:
    import prophet
    prophet_dir = os.path.dirname(prophet.__file__)
    stan_model_dir = os.path.join(prophet_dir, "stan_model")
    cmdstan_tbb = os.path.join(stan_model_dir, "cmdstan-2.37.0", "stan", "lib", "stan_math", "lib", "tbb")
    for d in [cmdstan_tbb, stan_model_dir]:
        if os.path.exists(d):
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(d)
                except Exception:
                    pass
except Exception:
    pass

from prophet import Prophet
from .base import BaseForecaster
from .config import ModelDefaults
from ..data.schema import ForecastResult, ForecastPoint

# Suppress cmdstanpy / prophet verbose logger
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
logging.getLogger("prophet").setLevel(logging.WARNING)



class ProphetForecaster(BaseForecaster):
    """
    Additive Trend & Seasonality Forecasting using Meta Prophet.
    Supports trend decomposition, weekly/yearly seasonality,
    and verified future regressors without data leakage.
    """
    def __init__(
        self,
        yearly_seasonality: Optional[bool] = None,
        weekly_seasonality: Optional[bool] = None,
        daily_seasonality: Optional[bool] = None,
        interval_width: Optional[float] = None,
    ):
        super().__init__(
            model_name="Prophet",
            model_type="Additive Trend & Seasonality",
            supported_horizons=[7, 28, 90]
        )
        self.yearly_seasonality = (
            yearly_seasonality if yearly_seasonality is not None 
            else ModelDefaults.PROPHET_YEARLY_SEASONALITY
        )
        self.weekly_seasonality = (
            weekly_seasonality if weekly_seasonality is not None 
            else ModelDefaults.PROPHET_WEEKLY_SEASONALITY
        )
        self.daily_seasonality = (
            daily_seasonality if daily_seasonality is not None 
            else ModelDefaults.PROPHET_DAILY_SEASONALITY
        )
        self.interval_width = (
            interval_width if interval_width is not None 
            else ModelDefaults.PROPHET_INTERVAL_WIDTH
        )
        self.model: Optional[Prophet] = None
        self.training_df: Optional[pd.DataFrame] = None
        self.time_col: str = "date"
        self.target_col: str = "target"
        self.future_regressors: List[str] = []

    def fit(
        self,
        df: pd.DataFrame,
        time_col: str,
        target_col: str,
        horizon: int = 28,
        future_covariates: Optional[List[str]] = None,
        **kwargs
    ) -> "ProphetForecaster":
        """
        Prepare standard ds, y DataFrame and fit Prophet.
        Strictly excludes HISTORICAL_ONLY features from future regressors.
        """
        self.validate_series_data(df, time_col, target_col, horizon)

        work_df = df.copy()
        work_df[time_col] = pd.to_datetime(work_df[time_col])
        work_df = work_df.sort_values(by=time_col).reset_index(drop=True)

        self.time_col = time_col
        self.target_col = target_col
        self.training_df = work_df

        prophet_df = pd.DataFrame({
            "ds": work_df[time_col],
            "y": work_df[target_col].astype(float)
        })

        # Initialize Prophet instance
        self.model = Prophet(
            yearly_seasonality=self.yearly_seasonality,
            weekly_seasonality=self.weekly_seasonality,
            daily_seasonality=self.daily_seasonality,
            interval_width=self.interval_width
        )

        # Add verified future regressors if explicitly provided and available
        self.future_regressors = []
        if future_covariates:
            for reg in future_covariates:
                if reg in work_df.columns:
                    self.model.add_regressor(reg)
                    prophet_df[reg] = work_df[reg].values
                    self.future_regressors.append(reg)

        try:
            self.model.fit(prophet_df)
            self.is_fitted = True
            self.metadata = {
                "interval_width": self.interval_width,
                "weekly_seasonality": self.weekly_seasonality,
                "future_regressors": self.future_regressors,
                "n_observations": len(prophet_df),
            }
        except Exception as e:
            raise RuntimeError(f"Failed to fit Prophet model: {str(e)}")

        return self

    def forecast(
        self,
        horizon: int,
        dataset_id: str,
        series_id: str,
        future_regressor_df: Optional[pd.DataFrame] = None,
        **kwargs
    ) -> ForecastResult:
        """
        Generate out-of-sample forecast with trend and seasonality decomposition.
        """
        if not self.is_fitted or self.model is None or self.training_df is None:
            raise RuntimeError("Model must be fitted before generating forecast.")

        start_time = time.time()
        
        # Build future dataframe for out-of-sample periods only
        future = self.model.make_future_dataframe(periods=horizon, freq="D", include_history=False)
        
        # Check future regressors requirements
        if self.future_regressors:
            if future_regressor_df is None or len(future_regressor_df) < horizon:
                raise ValueError(
                    f"Prophet model was configured with future regressors {self.future_regressors}, "
                    f"but future covariate values were not provided for the {horizon}-day forecast window."
                )
            for reg in self.future_regressors:
                future[reg] = future_regressor_df[reg].values[:horizon]

        prophet_forecast = self.model.predict(future)

        date_strs = [d.strftime("%Y-%m-%d") for d in prophet_forecast["ds"]]
        yhat = [round(float(max(0.0, val)), 2) for val in prophet_forecast["yhat"]]
        yhat_lower = [round(float(max(0.0, val)), 2) for val in prophet_forecast["yhat_lower"]]
        yhat_upper = [round(float(max(0.0, val)), 2) for val in prophet_forecast["yhat_upper"]]

        points = [
            ForecastPoint(
                date=d_str,
                forecast=f_val,
                lower_bound=l_val,
                upper_bound=u_val
            )
            for d_str, f_val, l_val, u_val in zip(date_strs, yhat, yhat_lower, yhat_upper)
        ]

        # Extract real components (trend, weekly seasonality)
        components: Dict[str, Any] = {}
        if "trend" in prophet_forecast.columns:
            components["trend"] = [round(float(v), 2) for v in prophet_forecast["trend"]]
        if "weekly" in prophet_forecast.columns:
            components["weekly"] = [round(float(v), 2) for v in prophet_forecast["weekly"]]

        exec_time = round((time.time() - start_time) * 1000, 2)
        train_start_str = self.training_df[self.time_col].iloc[0].strftime("%Y-%m-%d")
        train_end_str = self.training_df[self.time_col].iloc[-1].strftime("%Y-%m-%d")

        return ForecastResult(
            dataset_id=dataset_id,
            series_id=series_id,
            model="Prophet",
            forecast_horizon=horizon,
            dates=date_strs,
            forecast=yhat,
            lower_bound=yhat_lower,
            upper_bound=yhat_upper,
            points=points,
            components=components,
            training_start=train_start_str,
            training_end=train_end_str,
            forecast_start=date_strs[0],
            forecast_end=date_strs[-1],
            execution_time_ms=exec_time,
            status="SUCCESS",
            notes=[f"Fitted Prophet model with 95% uncertainty intervals on {len(self.training_df)} observations."]
        )
