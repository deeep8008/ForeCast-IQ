from typing import Tuple, Optional, Dict, Any
import pandas as pd
from app.core.exceptions import SplitError

class ChronologicalSplitter:
    """Performs strict temporal train/test splitting without lookahead data leakage."""

    @staticmethod
    def split(
        df_canonical: pd.DataFrame,
        train_percentage: float = 0.80,
        fixed_test_days: Optional[int] = None,
        series_id: Optional[str] = None
    ) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
        """
        Splits canonical data chronologically:
        - If series_id is specified, filters by that series.
        - Splits temporally such that test set strictly contains the latest observations.
        - Guarantees 0% data leakage.
        """
        if df_canonical.empty:
            raise SplitError("Cannot split an empty dataset.")

        df = df_canonical.copy()
        if series_id:
            df["_series_str"] = df["series_id"].astype(str)
            target_str = str(series_id)
            filtered = df[df["_series_str"] == target_str].copy()
            if filtered.empty:
                # If requested series_id is invalid or from a previous dataset, fallback to first available series
                available = df["series_id"].dropna().unique()
                if len(available) > 0:
                    filtered = df[df["series_id"] == available[0]].copy()
            if filtered.empty:
                raise SplitError(f"Series ID '{series_id}' not found in dataset.")
            df = filtered.drop(columns=["_series_str"], errors="ignore")

        # Sort strictly by timestamp
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        unique_timestamps = sorted(df["timestamp"].unique())
        total_steps = len(unique_timestamps)

        if total_steps < 5:
            raise SplitError(f"Dataset has only {total_steps} distinct time points. At least 5 are required for splitting.")

        # Calculate cutoff point
        if fixed_test_days is not None:
            if fixed_test_days >= total_steps:
                raise SplitError(f"Fixed test days ({fixed_test_days}) exceeds or equals total timestamps ({total_steps}).")
            train_steps = total_steps - fixed_test_days
            test_steps = fixed_test_days
        else:
            train_steps = int(total_steps * train_percentage)
            # Ensure at least 1 test step and 2 train steps
            train_steps = max(2, min(train_steps, total_steps - 1))
            test_steps = total_steps - train_steps

        cutoff_timestamp = unique_timestamps[train_steps - 1]
        
        # Partition data
        train_df = df[df["timestamp"] <= cutoff_timestamp].reset_index(drop=True)
        test_df = df[df["timestamp"] > cutoff_timestamp].reset_index(drop=True)

        train_start = str(train_df["timestamp"].min().date())
        train_end = str(train_df["timestamp"].max().date())
        test_start = str(test_df["timestamp"].min().date())
        test_end = str(test_df["timestamp"].max().date())

        actual_train_pct = round((train_steps / total_steps) * 100, 1)
        actual_test_pct = round((test_steps / total_steps) * 100, 1)

        metadata = {
            "total_observations": len(df),
            "total_timesteps": total_steps,
            "train_observations": len(train_df),
            "test_observations": len(test_df),
            "train_steps": train_steps,
            "test_steps": test_steps,
            "train_percentage": actual_train_pct,
            "test_percentage": actual_test_pct,
            "train_window": {
                "start_date": train_start,
                "end_date": train_end,
                "count": train_steps
            },
            "test_window": {
                "start_date": test_start,
                "end_date": test_end,
                "count": test_steps
            }
        }

        return train_df, test_df, metadata
