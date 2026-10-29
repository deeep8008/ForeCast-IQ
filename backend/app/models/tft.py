"""
Temporal Fusion Transformer (TFT) Forecasting Model Implementation (Phase 6)
ForecastIQ Backend

Architecture:
- Darts TFTModel with multi-horizon attention and specialized variable selection.
- Multi-horizon forecasting across 7D, 28D, and 90D horizons.
- Automatic target standardization via Darts Scaler fitted strictly on training data
  to prevent data leakage across validation/test/future horizons.
- Time-dependent known future feature encoding via `add_relative_index=True`.
- Non-negative clipping for retail demand/sales.
- Output: Standardized ForecastResult with quantile prediction bounds (P10 - P90) computed from TFT output quantiles.
"""
import os
import time
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

from darts import TimeSeries
from darts.models import TFTModel
from darts.dataprocessing.transformers import Scaler

from .base import BaseForecaster
from .config import ModelDefaults
from ..data.schema import ForecastResult, ForecastPoint


class TftForecaster(BaseForecaster):
    """
    Temporal Fusion Transformer (TFT) Forecaster using Darts.
    Supports multi-horizon forecasting with self-attention and relative index future encoding.
    """
    def __init__(
        self,
        input_chunk_length: Optional[int] = None,
        output_chunk_length: Optional[int] = None,
        epochs: Optional[int] = None,
        batch_size: Optional[int] = None,
        hidden_size: Optional[int] = None,
        lstm_layers: Optional[int] = None,
        num_attention_heads: Optional[int] = None,
        dropout: Optional[float] = None,
        random_state: Optional[int] = None,
    ):
        super().__init__(
            model_name="Temporal Fusion Transformer (TFT)",
            model_type="Multi-Horizon Attention Architecture",
            supported_horizons=[7, 28, 90]
        )
        self.input_chunk_length = input_chunk_length if input_chunk_length is not None else ModelDefaults.TFT_INPUT_CHUNK_LENGTH
        self.output_chunk_length = output_chunk_length if output_chunk_length is not None else ModelDefaults.TFT_OUTPUT_CHUNK_LENGTH
        self.epochs = epochs if epochs is not None else ModelDefaults.TFT_EPOCHS
        self.batch_size = batch_size if batch_size is not None else ModelDefaults.TFT_BATCH_SIZE
        self.hidden_size = hidden_size if hidden_size is not None else ModelDefaults.TFT_HIDDEN_SIZE
        self.lstm_layers = lstm_layers if lstm_layers is not None else ModelDefaults.TFT_LSTM_LAYERS
        self.num_attention_heads = num_attention_heads if num_attention_heads is not None else ModelDefaults.TFT_ATTENTION_HEADS
        self.dropout = dropout if dropout is not None else ModelDefaults.TFT_DROPOUT
        self.random_state = random_state if random_state is not None else ModelDefaults.TFT_RANDOM_STATE

        self.model: Optional[TFTModel] = None
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
    ) -> "TftForecaster":
        """
        Convert canonical dataframe to Darts TimeSeries, fit Scaler strictly on training history,
        and train Temporal Fusion Transformer model.
        """
        self.validate_series_data(df, time_col, target_col, horizon)

        work_df = df.copy()
        work_df[time_col] = pd.to_datetime(work_df[time_col])
        work_df = work_df.sort_values(by=time_col).reset_index(drop=True)

        self.time_col = time_col
        self.target_col = target_col
        self.last_timestamp = work_df[time_col].iloc[-1]

        # Configure dynamic input chunk length based on history and requested horizon
        output_len = min(self.output_chunk_length, horizon)
        input_len = self.input_chunk_length
        # Ensure training requirements: length must exceed input_chunk_length + output_chunk_length
        if len(work_df) <= input_len + output_len:
            input_len = max(3, (len(work_df) - output_len) // 2)

        try:
            ts = TimeSeries.from_dataframe(
                work_df,
                time_col=time_col,
                value_cols=target_col,
                fill_missing_dates=True,
                freq="D"
            )
        except Exception:
            ts = TimeSeries.from_dataframe(
                work_df,
                time_col=time_col,
                value_cols=target_col
            )

        # Scale target strictly on training observations
        self.scaler = Scaler()
        scaled_ts = self.scaler.fit_transform(ts)
        self.training_series = scaled_ts

        pl_trainer_kwargs = {
            "enable_progress_bar": False,
            "enable_model_summary": False,
            "accelerator": "cpu",
            "logger": False,
        }

        self.model = TFTModel(
            input_chunk_length=input_len,
            output_chunk_length=output_len,
            hidden_size=self.hidden_size,
            lstm_layers=self.lstm_layers,
            num_attention_heads=self.num_attention_heads,
            dropout=self.dropout,
            batch_size=self.batch_size,
            n_epochs=self.epochs,
            add_relative_index=True,
            random_state=self.random_state,
            pl_trainer_kwargs=pl_trainer_kwargs,
        )

        try:
            self.model.fit(scaled_ts)
            self.is_fitted = True
            self.metadata = {
                "input_chunk_length": input_len,
                "output_chunk_length": output_len,
                "hidden_size": self.hidden_size,
                "lstm_layers": self.lstm_layers,
                "attention_heads": self.num_attention_heads,
                "epochs": self.epochs,
                "batch_size": self.batch_size,
                "training_observations": len(ts),
            }
        except Exception as e:
            raise RuntimeError(f"TFT training failed: {str(e)}")

        return self

    def forecast(
        self,
        horizon: int,
        dataset_id: str,
        series_id: str,
        **kwargs
    ) -> ForecastResult:
        """
        Generate multi-horizon forecast using trained Temporal Fusion Transformer.
        """
        if not self.is_fitted or self.model is None or self.training_series is None or self.scaler is None:
            raise RuntimeError("Model must be fitted before generating forecast.")

        start_time = time.time()

        try:
            # Predict scaled multi-horizon outputs (with default samples for quantile bounds)
            pred_scaled = self.model.predict(
                n=horizon,
                series=self.training_series,
                num_samples=50
            )
            pred_unscaled = self.scaler.inverse_transform(pred_scaled)
        except Exception as e:
            raise RuntimeError(f"TFT forecast execution error: {str(e)}")

        mean_vals = pred_unscaled.mean().values().flatten()
        q10_vals = pred_unscaled.quantile(0.10).values().flatten()
        q90_vals = pred_unscaled.quantile(0.90).values().flatten()

        future_dates = [
            ts.strftime("%Y-%m-%d") if hasattr(ts, "strftime") else str(ts)[:10]
            for ts in pred_unscaled.time_index
        ]

        forecast_list: List[float] = [round(max(0.0, float(v)), 2) for v in mean_vals[:horizon]]
        lower_list: List[float] = [round(max(0.0, float(v)), 2) for v in q10_vals[:horizon]]
        upper_list: List[float] = [round(max(0.0, float(v)), 2) for v in q90_vals[:horizon]]

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
            model="Temporal Fusion Transformer (TFT)",
            forecast_horizon=horizon,
            dates=future_dates,
            forecast=forecast_list,
            lower_bound=lower_list,
            upper_bound=upper_list,
            points=points,
            components={
                "architecture": "Temporal Fusion Transformer (TFT) with Self-Attention",
                "input_chunk_length": self.metadata.get("input_chunk_length", self.input_chunk_length),
                "output_chunk_length": self.metadata.get("output_chunk_length", self.output_chunk_length),
                "hidden_size": self.hidden_size,
                "lstm_layers": self.lstm_layers,
                "attention_heads": self.num_attention_heads,
                "epochs": self.epochs,
                "uncertainty_method": "TFT Quantile Loss Prediction Intervals (P10 - P90)",
            },
            training_start=start_str,
            training_end=end_str,
            forecast_start=future_dates[0],
            forecast_end=future_dates[-1],
            execution_time_ms=exec_time,
            status="SUCCESS",
            notes=[
                f"Trained Temporal Fusion Transformer on {self.metadata.get('training_observations', 0)} historical steps.",
                f"Generated {horizon}-day multi-horizon forecast using multi-head self-attention and dynamic temporal encoding.",
                "Target normalization parameters were fitted exclusively on historical training data."
            ]
        )

    def save(self, filepath: str) -> None:
        """Save fitted TFT model artifact to disk."""
        if not self.is_fitted or self.model is None:
            raise RuntimeError("Cannot save unfitted model.")
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        self.model.save(filepath)

    def load(self, filepath: str) -> "TftForecaster":
        """Load trained TFT model artifact from disk."""
        self.model = TFTModel.load(filepath)
        self.is_fitted = True
        return self
