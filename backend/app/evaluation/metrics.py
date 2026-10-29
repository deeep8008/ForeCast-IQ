"""
Evaluation Metrics for Time-Series Forecasting (Phase 8)
ForecastIQ Backend

Implements:
1. MAPE (Mean Absolute Percentage Error) with strict zero-actual policy:
   - Excludes zero actual values to prevent division by zero and arbitrary infinity distortions.
   - Reports valid count, zero actual count, and total count.
   - If all actual values are zero, returns None (not-defined) rather than misleading zero.
2. RMSE (Root Mean Squared Error):
   - Computes square root of mean squared deviations between actual and predicted values.
"""
from typing import List, Dict, Any, Optional, Tuple, Union
import numpy as np


class EvaluationMetrics:
    """
    Robust time-series forecasting evaluation metrics.
    """

    @classmethod
    def calculate_mape(
        cls,
        actuals: List[float],
        predictions: List[float]
    ) -> Dict[str, Any]:
        """
        Calculate MAPE with documented zero-actual policy:
        - Absolute percentage error: |actual - pred| / actual
        - Observations where actual == 0 are strictly excluded from the denominator.
        - Returns:
            mape: Optional[float] (percentage 0-100%, or None if no valid non-zero actuals)
            mape_valid_count: int
            mape_zero_actual_count: int
            total_count: int
        """
        if len(actuals) != len(predictions):
            raise ValueError(
                f"Length mismatch: actuals has {len(actuals)} items, "
                f"predictions has {len(predictions)} items."
            )

        total_count = len(actuals)
        if total_count == 0:
            return {
                "mape": None,
                "mape_valid_count": 0,
                "mape_zero_actual_count": 0,
                "total_count": 0,
                "note": "Empty sequence; cannot compute MAPE."
            }

        valid_apes: List[float] = []
        zero_actual_count = 0

        for act, pred in zip(actuals, predictions):
            act_f = float(act)
            pred_f = float(pred)

            if act_f == 0.0 or np.isclose(act_f, 0.0):
                zero_actual_count += 1
            else:
                ape = abs(act_f - pred_f) / abs(act_f)
                valid_apes.append(ape)

        valid_count = len(valid_apes)

        if valid_count == 0:
            return {
                "mape": None,
                "mape_valid_count": 0,
                "mape_zero_actual_count": zero_actual_count,
                "total_count": total_count,
                "note": "All actual observations are zero; MAPE is undefined by zero-actual policy."
            }

        mean_ape = float(np.mean(valid_apes))
        mape_percentage = round(mean_ape * 100.0, 2)

        return {
            "mape": mape_percentage,
            "mape_valid_count": valid_count,
            "mape_zero_actual_count": zero_actual_count,
            "total_count": total_count,
            "note": f"Evaluated on {valid_count}/{total_count} non-zero actual observations."
        }

    @classmethod
    def calculate_rmse(
        cls,
        actuals: List[float],
        predictions: List[float]
    ) -> Dict[str, Any]:
        """
        Calculate RMSE (Root Mean Squared Error).
        """
        if len(actuals) != len(predictions):
            raise ValueError(
                f"Length mismatch: actuals has {len(actuals)} items, "
                f"predictions has {len(predictions)} items."
            )

        sample_count = len(actuals)
        if sample_count == 0:
            return {
                "rmse": None,
                "sample_count": 0
            }

        act_arr = np.array(actuals, dtype=float)
        pred_arr = np.array(predictions, dtype=float)

        squared_errors = (act_arr - pred_arr) ** 2
        mean_squared_error = float(np.mean(squared_errors))
        rmse_val = round(float(np.sqrt(mean_squared_error)), 2)

        return {
            "rmse": rmse_val,
            "sample_count": sample_count
        }

    @classmethod
    def evaluate_forecast(
        cls,
        actuals: List[float],
        predictions: List[float]
    ) -> Dict[str, Any]:
        """
        Compute both MAPE and RMSE and package standardized metrics dictionary.
        """
        mape_res = cls.calculate_mape(actuals, predictions)
        rmse_res = cls.calculate_rmse(actuals, predictions)

        return {
            "mape": mape_res["mape"],
            "rmse": rmse_res["rmse"],
            "mape_valid_count": mape_res["mape_valid_count"],
            "mape_zero_actual_count": mape_res["mape_zero_actual_count"],
            "sample_count": rmse_res["sample_count"],
            "note": mape_res.get("note", "")
        }
