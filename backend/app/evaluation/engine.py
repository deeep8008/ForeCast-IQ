import time
from typing import Dict, Any, List
from dataclasses import dataclass, field
import pandas as pd
import numpy as np

from app.models.base_forecaster import BaseForecaster, ForecastOutput
from app.evaluation.metrics import Metrics
from app.core.exceptions import PreprocessingError

@dataclass
class AlignedPredictionPoint:
    timestamp: str
    actual: float
    predicted: float

@dataclass
class ModelEvaluationResult:
    model_name: str
    model_key: str
    model_type: str
    mape: float
    rmse: float
    mae: float
    wape: float
    train_time_seconds: float
    train_window_start: str
    train_window_end: str
    test_window_start: str
    test_window_end: str
    horizon_steps: int
    predictions: List[float]
    actuals: List[float]
    timestamps: List[str]
    aligned_series: List[Dict[str, Any]]
    lower_bound_80: List[float] = field(default_factory=list)
    upper_bound_80: List[float] = field(default_factory=list)
    lower_bound_95: List[float] = field(default_factory=list)
    upper_bound_95: List[float] = field(default_factory=list)
    status: str = "evaluated"

class EvaluationEngine:
    """
    Model-Agnostic Backtesting & Evaluation Engine.
    Operates strictly through the BaseForecaster interface with zero model-specific branching.
    """

    @staticmethod
    def evaluate_model(
        model: BaseForecaster,
        model_key: str,
        train_df: pd.DataFrame,
        test_df: pd.DataFrame
    ) -> ModelEvaluationResult:
        if train_df.empty or test_df.empty:
            raise PreprocessingError("Both train_df and test_df must be non-empty for historical evaluation.")

        train_df = train_df.copy()
        test_df = test_df.copy()
        train_df["timestamp"] = pd.to_datetime(train_df["timestamp"])
        test_df["timestamp"] = pd.to_datetime(test_df["timestamp"])

        # Strict Data Leakage Assertion
        max_train_time = train_df["timestamp"].max()
        min_test_time = test_df["timestamp"].min()

        if max_train_time >= min_test_time:
            raise PreprocessingError(
                f"Data leakage detected in evaluation engine! "
                f"Training end date ({max_train_time}) must strictly precede test start date ({min_test_time})."
            )

        # 1. Fit strictly on the training partition (Test partition is hidden)
        start_fit = time.time()
        model.fit(train_df)
        train_duration = round(time.time() - start_fit, 3)

        # 2. Predict the exact length of the hidden test period
        horizon = len(test_df)
        forecast_output: ForecastOutput = model.predict(horizon_steps=horizon)

        # 3. Extract actual values and predictions
        y_true = test_df["target"].values.astype(float)
        y_pred = np.array(forecast_output.predictions, dtype=float)
        y_pred = np.nan_to_num(y_pred, nan=float(np.mean(y_true) if len(y_true) > 0 else 0.0))

        # 4. Compute metrics
        mape_score = Metrics.mape(y_true, y_pred)
        rmse_score = Metrics.rmse(y_true, y_pred)
        mae_score = Metrics.mae(y_true, y_pred)
        wape_score = Metrics.wape(y_true, y_pred)

        # 5. Build 1-to-1 aligned prediction objects for frontend visualization
        aligned_series = []
        test_timestamps = [str(ts.date()) for ts in test_df["timestamp"]]
        for t_stamp, actual_val, pred_val in zip(test_timestamps, y_true, y_pred):
            p_val = float(pred_val) if not np.isnan(pred_val) else 0.0
            aligned_series.append({
                "timestamp": t_stamp,
                "actual": round(float(actual_val), 3),
                "predicted": round(p_val, 3)
            })

        return ModelEvaluationResult(
            model_name=model.name,
            model_key=model_key,
            model_type=model.model_type,
            mape=mape_score,
            rmse=rmse_score,
            mae=mae_score,
            wape=wape_score,
            train_time_seconds=train_duration,
            train_window_start=str(train_df["timestamp"].min().date()),
            train_window_end=str(max_train_time.date()),
            test_window_start=str(min_test_time.date()),
            test_window_end=str(test_df["timestamp"].max().date()),
            horizon_steps=horizon,
            predictions=[round(float(p), 3) for p in y_pred],
            actuals=[round(float(a), 3) for a in y_true],
            timestamps=test_timestamps,
            aligned_series=aligned_series,
            lower_bound_80=forecast_output.lower_bound_80 or [],
            upper_bound_80=forecast_output.upper_bound_80 or [],
            lower_bound_95=forecast_output.lower_bound_95 or [],
            upper_bound_95=forecast_output.upper_bound_95 or [],
            status="evaluated"
        )
