import numpy as np
from typing import Union, List

class Metrics:
    """
    Pure mathematical evaluation metrics for time-series forecasting.
    Includes zero-division safety rules.
    """

    @staticmethod
    def rmse(y_true: Union[np.ndarray, List[float]], y_pred: Union[np.ndarray, List[float]]) -> float:
        """
        Root Mean Squared Error: sqrt( 1/N * sum((y_true - y_pred)^2) )
        Expressed in original target units.
        """
        y_t = np.asarray(y_true, dtype=float)
        y_p = np.asarray(y_pred, dtype=float)

        if len(y_t) == 0:
            return 0.0

        diff = y_t - y_p
        diff = np.nan_to_num(diff, nan=9999.0, posinf=9999.0, neginf=-9999.0)
        mse = np.mean(diff ** 2)
        val = float(np.sqrt(mse))
        if np.isnan(val) or np.isinf(val):
            return 9999.0
        return round(val, 4)

    @staticmethod
    def mae(y_true: Union[np.ndarray, List[float]], y_pred: Union[np.ndarray, List[float]]) -> float:
        """
        Mean Absolute Error: 1/N * sum(|y_true - y_pred|)
        """
        y_t = np.asarray(y_true, dtype=float)
        y_p = np.asarray(y_pred, dtype=float)

        if len(y_t) == 0:
            return 0.0

        diff = np.abs(y_t - y_p)
        diff = np.nan_to_num(diff, nan=9999.0, posinf=9999.0, neginf=9999.0)
        val = float(np.mean(diff))
        if np.isnan(val) or np.isinf(val):
            return 9999.0
        return round(val, 4)

    @staticmethod
    def mape(
        y_true: Union[np.ndarray, List[float]],
        y_pred: Union[np.ndarray, List[float]],
        epsilon: float = 1e-8
    ) -> float:
        y_t = np.asarray(y_true, dtype=float)
        y_p = np.asarray(y_pred, dtype=float)

        if len(y_t) == 0:
            return 0.0

        # Replace any NaNs in predictions with fallback
        y_p = np.nan_to_num(y_p, nan=0.0, posinf=9999.0, neginf=0.0)

        # Mask non-zero actual observations
        non_zero_mask = y_t != 0

        if np.any(non_zero_mask):
            pct_errors = np.abs((y_t[non_zero_mask] - y_p[non_zero_mask]) / y_t[non_zero_mask])
            mape_value = float(np.mean(pct_errors) * 100.0)
        else:
            if np.all(y_p == 0):
                mape_value = 0.0
            else:
                pct_errors = np.abs((y_t - y_p) / np.maximum(np.abs(y_t), epsilon))
                mape_value = float(np.mean(pct_errors) * 100.0)

        if np.isnan(mape_value) or np.isinf(mape_value):
            return 9999.0
        return round(min(9999.0, mape_value), 4)

    @staticmethod
    def wape(y_true: Union[np.ndarray, List[float]], y_pred: Union[np.ndarray, List[float]]) -> float:
        """
        Weighted Absolute Percentage Error: sum(|y_true - y_pred|) / sum(|y_true|) * 100%
        """
        y_t = np.asarray(y_true, dtype=float)
        y_p = np.asarray(y_pred, dtype=float)
        y_p = np.nan_to_num(y_p, nan=0.0)

        sum_actual = np.sum(np.abs(y_t))
        if sum_actual == 0:
            return 0.0 if np.sum(np.abs(y_p)) == 0 else 100.0

        val = float((np.sum(np.abs(y_t - y_p)) / sum_actual) * 100.0)
        if np.isnan(val) or np.isinf(val):
            return 9999.0
        return round(val, 4)
