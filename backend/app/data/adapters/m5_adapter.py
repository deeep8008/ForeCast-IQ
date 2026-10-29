"""
M5 Dataset Adapter
Converts M5 Forecasting Accuracy source structure into the canonical schema.
ForecastIQ Backend
"""
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np


class M5Adapter:
    """
    Adapter to convert wide/hierarchical M5 data format into the canonical
    time-series format: date, series_id, target, and optional canonical features.
    """

    @staticmethod
    def transform_sales_wide_to_canonical(
        sales_df: pd.DataFrame,
        calendar_df: Optional[pd.DataFrame] = None,
        prices_df: Optional[pd.DataFrame] = None,
        max_series: int = 10,
        max_days: int = 90
    ) -> pd.DataFrame:
        """
        Melts wide M5 sales data (d_1 ... d_1913) into canonical long format,
        and optionally merges calendar and price covariates.
        """
        # 1. Select subset of series for responsive processing
        id_cols = [c for c in ["id", "item_id", "dept_id", "cat_id", "store_id", "state_id"] if c in sales_df.columns]
        day_cols = [c for c in sales_df.columns if c.startswith("d_")]

        if not day_cols:
            raise ValueError("Sales dataframe does not contain M5 daily columns (d_1, d_2, ...).")

        # Take the most recent max_days
        selected_day_cols = day_cols[-max_days:]
        subset_sales = sales_df.head(max_series)[id_cols + selected_day_cols]

        # 2. Melt to long format
        melted = subset_sales.melt(
            id_vars=id_cols,
            value_vars=selected_day_cols,
            var_name="d",
            value_name="target"
        )

        # 3. Create canonical series_id
        if "id" in melted.columns:
            # Strip _validation or _evaluation suffix
            melted["series_id"] = melted["id"].astype(str).str.replace("_validation", "", regex=False).str.replace("_evaluation", "", regex=False)
        else:
            melted["series_id"] = melted.get("item_id", "ITEM") + "_" + melted.get("store_id", "STORE")

        # 4. Map calendar dates (d -> date)
        if calendar_df is not None and "d" in calendar_df.columns and "date" in calendar_df.columns:
            cal_subset = calendar_df[["d", "date", "wm_yr_wk", "event_name_1"]].copy()
            merged = melted.merge(cal_subset, on="d", how="left")
            merged["holiday"] = merged["event_name_1"].fillna("")
        else:
            # Fallback date mapping assuming d_1 is 2011-01-29
            # For d_x, calculate date offset
            day_nums = melted["d"].str.replace("d_", "", regex=False).astype(int)
            base_date = pd.Timestamp("2011-01-29")
            merged = melted.copy()
            merged["date"] = [
                (base_date + pd.Timedelta(days=d_num - 1)).strftime("%Y-%m-%d")
                for d_num in day_nums
            ]

        # 5. Map sell prices if available
        if prices_df is not None and "wm_yr_wk" in merged.columns:
            price_cols = [c for c in ["store_id", "item_id", "wm_yr_wk", "sell_price"] if c in prices_df.columns]
            if len(price_cols) == 4:
                merged = merged.merge(prices_df[price_cols], on=["store_id", "item_id", "wm_yr_wk"], how="left")
                # Keep NaN for rows with no matching price record.
                # Filling with 0.0 would cause missing prices to appear as genuine zero prices
                # in the insights engine, producing "$0.00" averages for stores like CA_2/CA_3
                # whose sell_price rows were absent from the loaded prices slice.
                merged["price"] = merged["sell_price"]  # preserves NaN for unmatched rows

        # 6. Build final Canonical DataFrame
        canonical_df = pd.DataFrame()
        canonical_df["date"] = merged["date"]
        canonical_df["series_id"] = merged["series_id"]
        canonical_df["target"] = pd.to_numeric(merged["target"], errors="coerce").fillna(0.0)

        # Optional canonical fields
        if "store_id" in merged.columns:
            canonical_df["store_id"] = merged["store_id"]
        if "item_id" in merged.columns:
            canonical_df["item_id"] = merged["item_id"]
        if "cat_id" in merged.columns:
            canonical_df["category"] = merged["cat_id"]
        if "state_id" in merged.columns:
            canonical_df["state"] = merged["state_id"]
        if "price" in merged.columns:
            canonical_df["price"] = merged["price"]
        if "holiday" in merged.columns:
            canonical_df["holiday"] = merged["holiday"]

        # Sort chronologically by series_id and date
        canonical_df = canonical_df.sort_values(by=["series_id", "date"]).reset_index(drop=True)
        return canonical_df
