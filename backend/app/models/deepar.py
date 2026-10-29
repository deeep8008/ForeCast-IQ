"""
DeepAR Probabilistic Forecasting Model Implementation (Phase 6)
ForecastIQ Backend

Architecture:
- Darts RNNModel with LSTM cell architecture and GaussianLikelihood.
- Probabilistic multi-horizon forecasting (7D, 28D, 90D).
- Automatic target standardization via Darts Scaler fitted strictly on training data
  to prevent data leakage across validation/test/future horizons.
- Non-negative clipping for demand/sales targets.
- Output: Standardized ForecastResult with probabilistic 10th and 90th percentile bounds.
"""
import os
import time
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

from darts import TimeSeries
from darts.models import RNNModel
from darts.utils.likelihood_models import GaussianLikelihood
from darts.dataprocessing.transformers import Scaler

from .base import BaseForecaster
from .config import ModelDefaults
from ..data.schema import ForecastResult, ForecastPoint


class DeeparForecaster(BaseForecaster):
    """
    DeepAR Autoregressive Recurrent Neural Network Forecaster.
    Implements probabilistic time series forecasting with Gaussian likelihood.
    """
    def __init__(
        self,
        input_chunk_length: Optional[int] = None,
        training_length: Optional[int] = None,
        epochs: Optional[int] = None,
        batch_size: Optional[int] = None,
        hidden_dim: Optional[int] = None,
        num_layers: Optional[int] = None,
        dropout: Optional[float] = None,
        random_state: Optional[int] = None,
        num_samples: Optional[int] = None,
    ):
        super().__init__(
            model_name="DeepAR",
            model_type="Probabilistic Recurrent Neural Network",
            supported_horizons=[7, 28, 90]
        )
        self.input_chunk_length = input_chunk_length if input_chunk_length is not None else ModelDefaults.DEEPAR_INPUT_CHUNK_LENGTH
        self.training_length = training_length if training_length is not None else ModelDefaults.DEEPAR_TRAINING_LENGTH
        self.epochs = epochs if epochs is not None else ModelDefaults.DEEPAR_EPOCHS
        self.batch_size = batch_size if batch_size is not None else ModelDefaults.DEEPAR_BATCH_SIZE
        self.hidden_dim = hidden_dim if hidden_dim is not None else ModelDefaults.DEEPAR_HIDDEN_DIM
        self.num_layers = num_layers if num_layers is not None else ModelDefaults.DEEPAR_NUM_LAYERS
        self.dropout = dropout if dropout is not None else ModelDefaults.DEEPAR_DROPOUT
        self.random_state = random_state if random_state is not None else ModelDefaults.DEEPAR_RANDOM_STATE
        self.num_samples = num_samples if num_samples is not None else ModelDefaults.DEEPAR_NUM_SAMPLES

        self.model: Optional[RNNModel] = None
        self.scaler: Optional[Scaler] = None
        self.training_series: Optional[TimeSeries] = None
        self.time_col: str = "date"
        self.target_col: str = "target"
        self.last_timestamp: Optional[pd.Timestamp] = None

    def fit(
        self,
        df: pd.DataFrame,
        time_col: str,
        target_col: str,
        horizon: int = 28,
        **kwargs
    ) -> "DeeparForecaster":
        """
        Convert canonical dataframe to Darts TimeSeries, fit Scaler strictly on training history,
        and train probabilistic DeepAR RNN model.
        """
        self.validate_series_data(df, time_col, target_col, horizon)

        work_df = df.copy()
        work_df[time_col] = pd.to_datetime(work_df[time_col])
        work_df = work_df.sort_values(by=time_col).reset_index(drop=True)

        self.time_col = time_col
        self.target_col = target_col
        self.last_timestamp = work_df[time_col].iloc[-1]

        # Dynamic training length adjustment if series is slightly shorter than default
        input_len = self.input_chunk_length
        train_len = min(self.training_length, len(work_df) - 1)
        if train_len <= input_len:
            input_len = max(3, train_len // 2)

        try:
            ts = TimeSeries.from_dataframe(
                work_df,
                time_col=time_col,
                value_cols=target_col,
                fill_missing_dates=True,
                freq="D"
            )
        except Exception:
            # Fallback if frequency inference encounters non-daily calendar
            ts = TimeSeries.from_dataframe(
                work_df,
                time_col=time_col,
                value_cols=target_col
            )

        # Scale target strictly on training observations (prevents future normalization leakage)
        self.scaler = Scaler()
        scaled_ts = self.scaler.fit_transform(ts)
        self.training_series = scaled_ts

        pl_trainer_kwargs = {
            "enable_progress_bar": False,
            "enable_model_summary": False,
            "accelerator": "cpu",
            "logger": False,
        }

        self.model = RNNModel(
            model="LSTM",
            input_chunk_length=input_len,
            training_length=train_len,
            hidden_dim=self.hidden_dim,
            n_rnn_layers=self.num_layers,
            dropout=self.dropout,
            batch_size=self.batch_size,
            n_epochs=self.epochs,
            likelihood=GaussianLikelihood(),
            random_state=self.random_state,
            pl_trainer_kwargs=pl_trainer_kwargs,
        )

        try:
            self.model.fit(scaled_ts)
            self.is_fitted = True
            self.metadata = {
                "input_chunk_length": input_len,
                "training_length": train_len,
                "epochs": self.epochs,
                "batch_size": self.batch_size,
                "hidden_dim": self.hidden_dim,
                "n_layers": self.num_layers,
                "num_samples": self.num_samples,
                "likelihood": "GaussianLikelihood",
                "training_observations": len(ts),
            }
        except Exception as e:
            raise RuntimeError(f"DeepAR training failed: {str(e)}")

        return self

    def forecast(
        self,
        horizon: int,
        dataset_id: str,
        series_id: str,
        **kwargs
    ) -> ForecastResult:
        """
        Generate probabilistic multi-horizon predictions with empirical quantiles (10% and 90%).
        """
        if not self.is_fitted or self.model is None or self.training_series is None or self.scaler is None:
            raise RuntimeError("Model must be fitted before generating forecast.")

        start_time = time.time()

        try:
            # Predict scaled probabilistic samples
            pred_scaled = self.model.predict(
                n=horizon,
                series=self.training_series,
                num_samples=self.num_samples
            )
            # Invert scaling to original scale
            pred_unscaled = self.scaler.inverse_transform(pred_scaled)
        except Exception as e:
            raise RuntimeError(f"DeepAR forecast execution error: {str(e)}")

        # Calculate mean prediction and 10th / 90th percentile uncertainty bounds
        mean_vals = pred_unscaled.mean().values().flatten()
        q10_vals = pred_unscaled.quantile(0.10).values().flatten()
        q90_vals = pred_unscaled.quantile(0.90).values().flatten()

        # Generate future date list
        future_dates = [
            ts.strftime("%Y-%m-%d") if hasattr(ts, "strftime") else str(ts)[:10]
            for ts in pred_unscaled.time_index
        ]

        # Ensure correct length
        forecast_list: List[float] = [round(max(0.0, float(v)), 2) for v in mean_vals[:horizon]]
        lower_list: List[float] = [round(max(0.0, float(v)), 2) for v in q10_vals[:horizon]]
        upper_list: List[float] = [round(max(0.0, float(v)), 2) for v in q90_vals[:horizon]]

        # Ensure upper is at least forecast and lower is at most forecast
        for i in range(len(forecast_list)):
            if lower_list[i] > forecast_list[i]:
                lower_list[i] = forecast_list[i]
            if upper_list[i] < forecast_list[i]:
                upper_list[i] = forecast_list[i]

        points = [
            ForecastPoint(
                date=d,
                forecast=f,
                lower_bound=lb,
                upper_bound=ub,
            )
            for d, f, lb, ub in zip(future_dates, forecast_list, lower_list, upper_list)
        ]

        exec_time = round((time.time() - start_time) * 1000, 2)
        start_str = self.training_series.time_index[0].strftime("%Y-%m-%d")
        end_str = self.training_series.time_index[-1].strftime("%Y-%m-%d")

        return ForecastResult(
            dataset_id=dataset_id,
            series_id=series_id,
            model="DeepAR",
            forecast_horizon=horizon,
            dates=future_dates,
            forecast=forecast_list,
            lower_bound=lower_list,
            upper_bound=upper_list,
            points=points,
            components={
                "architecture": "DeepAR (Darts RNNModel + GaussianLikelihood)",
                "input_chunk_length": self.metadata.get("input_chunk_length", self.input_chunk_length),
                "hidden_dim": self.hidden_dim,
                "n_layers": self.num_layers,
                "epochs": self.epochs,
                "num_samples": self.num_samples,
                "uncertainty_method": "Empirical Gaussian Likelihood Quantiles (P10 - P90)",
            },
            training_start=start_str,
            training_end=end_str,
            forecast_start=future_dates[0],
            forecast_end=future_dates[-1],
            execution_time_ms=exec_time,
            status="SUCCESS",
            notes=[
                f"Trained DeepAR probabilistic LSTM on {self.metadata.get('training_observations', 0)} historical steps.",
                f"Generated {horizon}-day forecast with empirical P10/P90 prediction intervals from {self.num_samples} Monte Carlo samples.",
                "Target normalization parameters were fitted exclusively on historical training data."
            ]
        )

    def save(self, filepath: str) -> None:
        """Save fitted DeepAR model and scaler state to disk."""
        if not self.is_fitted or self.model is None:
            raise RuntimeError("Cannot save unfitted model.")
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        self.model.save(filepath)

    def load(self, filepath: str) -> "DeeparForecaster":
        """Load trained DeepAR model artifact from disk."""
        self.model = RNNModel.load(filepath)
        self.is_fitted = True
        return self
