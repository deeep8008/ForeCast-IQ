"""
Abstract Base Forecasting Model Interface (Phase 4)
ForecastIQ Backend
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import pandas as pd
from ..data.schema import ForecastResult, ForecastPoint


class BaseForecaster(ABC):
    """
    Common forecasting model interface supporting fit, predict, and forecast.
    All models must eventually produce a standardized ForecastResult.
    """
    def __init__(
        self,
        model_name: str,
        model_type: str,
        supported_horizons: Optional[List[int]] = None
    ):
        self.model_name = model_name
        self.model_type = model_type
        self.supported_horizons = supported_horizons or [7, 28, 90]
        self.is_fitted: bool = False
        self.metadata: Dict[str, Any] = {}

    @abstractmethod
    def fit(self, df: pd.DataFrame, time_col: str, target_col: str, **kwargs) -> "BaseForecaster":
        """Fit model parameters on historical training data."""
        pass

    @abstractmethod
    def forecast(
        self,
        horizon: int,
        dataset_id: str,
        series_id: str,
        **kwargs
    ) -> ForecastResult:
        """
        Generate out-of-sample future predictions for the specified horizon
        and return the standardized ForecastResult structure.
        """
        pass

    def validate_series_data(
        self,
        df: pd.DataFrame,
        time_col: str,
        target_col: str,
        horizon: int
    ) -> None:
        """
        Validate single-series data before fitting:
        - Must not be empty
        - Must be sorted by date
        - Target must be numeric
        - Must not contain NaN target values
        - Must have sufficient history for the requested horizon
        - Must not have zero variance (constant series) unless explicitly handled
        """
        if df.empty or len(df) == 0:
            raise ValueError(f"Series has no observations for model training.")

        if target_col not in df.columns or time_col not in df.columns:
            raise ValueError(f"Required column '{target_col}' or '{time_col}' missing from series dataframe.")

        # Check for unhandled missing values in target
        if df[target_col].isna().any():
            raise ValueError("Target contains unresolved missing values.")

        # Check numeric
        if not pd.api.types.is_numeric_dtype(df[target_col]):
            raise ValueError("Target contains non-numeric values.")

        # Check minimum history
        from .config import ModelDefaults
        min_required = ModelDefaults.MIN_OBSERVATIONS.get(horizon, horizon * 2)
        if len(df) < min_required:
            raise ValueError(
                "Not enough historical data for this forecast horizon. "
                f"Available: {len(df)} observations. Required: {min_required} observations."
            )

        # Check constant series
        if df[target_col].nunique() <= 1:
            raise ValueError("Series is constant (zero variance across all observations). Cannot fit statistical model.")
