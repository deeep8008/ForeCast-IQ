"""
SARIMA (Seasonal ARIMA) Forecasting Model Implementation (Phase 4)
ForecastIQ Backend
"""
import time
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
import statsmodels.api as sm
from .base import BaseForecaster
from .config import ModelDefaults
from ..data.schema import ForecastResult, ForecastPoint


class SarimaForecaster(BaseForecaster):
    """
    Seasonal Autoregressive Integrated Moving Average (SARIMA) model using statsmodels.
    Configurable order (p, d, q) and seasonal_order (P, D, Q, s).
    """
    def __init__(
        self,
        order: Optional[Tuple[int, int, int]] = None,
        seasonal_order: Optional[Tuple[int, int, int, int]] = None,
    ):
        super().__init__(
            model_name="SARIMA",
            model_type="Seasonal Statistical Baseline",
            supported_horizons=[7, 28, 90]
        )
        self.order: Tuple[int, int, int] = order or ModelDefaults.SARIMA_ORDER
        self.seasonal_order: Tuple[int, int, int, int] = seasonal_order or ModelDefaults.SARIMA_SEASONAL_ORDER
        self.fitted_model = None
        self.training_df: Optional[pd.DataFrame] = None
        self.time_col: str = "date"
        self.target_col: str = "target"

    def fit(self, df: pd.DataFrame, time_col: str, target_col: str, horizon: int = 28, **kwargs) -> "SarimaForecaster":
        """
        Validate single-series data, sort chronologically, and fit statsmodels SARIMAX.
        """
        self.validate_series_data(df, time_col, target_col, horizon)

        work_df = df.copy()
        work_df[time_col] = pd.to_datetime(work_df[time_col])
        work_df = work_df.sort_values(by=time_col).reset_index(drop=True)

        self.time_col = time_col
        self.target_col = target_col
        self.training_df = work_df

        target_series = work_df[target_col].astype(float).values

        try:
            model = sm.tsa.statespace.SARIMAX(
                target_series,
                order=self.order,
                seasonal_order=self.seasonal_order,
                enforce_stationarity=False,
                enforce_invertibility=False
            )
            self.fitted_model = model.fit(disp=False)
            self.is_fitted = True
            self.metadata = {
                "order": self.order,
                "seasonal_order": self.seasonal_order,
                "aic": float(self.fitted_model.aic) if hasattr(self.fitted_model, "aic") else None,
                "bic": float(self.fitted_model.bic) if hasattr(self.fitted_model, "bic") else None,
                "n_observations": len(target_series),
            }
        except Exception as e:
            raise RuntimeError(f"Failed to fit SARIMA{self.order}x{self.seasonal_order} model: {str(e)}")

        return self

    def forecast(
        self,
        horizon: int,
        dataset_id: str,
        series_id: str,
        **kwargs
    ) -> ForecastResult:
        """
        Produce seasonal future forecast for specified horizon with confidence intervals.
        """
        if not self.is_fitted or self.fitted_model is None or self.training_df is None:
            raise RuntimeError("Model must be fitted before generating forecast.")

        start_time = time.time()
        last_date = self.training_df[self.time_col].iloc[-1]
        future_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=horizon, freq="D")
        date_strs = [d.strftime("%Y-%m-%d") for d in future_dates]

        forecast_res = self.fitted_model.get_forecast(steps=horizon)
        predicted_mean = np.array(forecast_res.predicted_mean).tolist()
        predicted_mean = [round(float(max(0.0, val)), 2) for val in predicted_mean]

        conf_int = forecast_res.conf_int(alpha=0.05)
        lower_bound = [round(float(max(0.0, row[0])), 2) for row in conf_int]
        upper_bound = [round(float(max(0.0, row[1])), 2) for row in conf_int]

        points = [
            ForecastPoint(
                date=d_str,
                forecast=f_val,
                lower_bound=l_val,
                upper_bound=u_val
            )
            for d_str, f_val, l_val, u_val in zip(date_strs, predicted_mean, lower_bound, upper_bound)
        ]

        exec_time = round((time.time() - start_time) * 1000, 2)
        train_start_str = self.training_df[self.time_col].iloc[0].strftime("%Y-%m-%d")
        train_end_str = last_date.strftime("%Y-%m-%d")

        return ForecastResult(
            dataset_id=dataset_id,
            series_id=series_id,
            model=f"SARIMA{self.order}x{self.seasonal_order}",
            forecast_horizon=horizon,
            dates=date_strs,
            forecast=predicted_mean,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            points=points,
            components={
                "order": list(self.order),
                "seasonal_order": list(self.seasonal_order),
                "seasonal_period": self.seasonal_order[3],
                "aic": self.metadata.get("aic"),
                "bic": self.metadata.get("bic"),
            },
            training_start=train_start_str,
            training_end=train_end_str,
            forecast_start=date_strs[0],
            forecast_end=date_strs[-1],
            execution_time_ms=exec_time,
            status="SUCCESS",
            notes=[f"Fitted SARIMA with {self.seasonal_order[3]}-day seasonality on {len(self.training_df)} observations."]
        )
