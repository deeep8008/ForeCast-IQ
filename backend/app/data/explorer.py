"""
Data Explorer Analytics Engine (Full Dataset Analytics)
ForecastIQ Backend

Calculates comprehensive summary metrics, breakdowns, and trend trajectories
from the COMPLETE active dataset (never preview rows).
"""
from typing import Dict, Any, Optional, List
import pandas as pd
import numpy as np

from .schema import (
    ExplorerResponse,
    ExplorerScope,
    ExplorerDimensions,
    ExplorerAvailableFilters,
    ExplorerTrendPoint,
    ExplorerBreakdownItem,
)
from .loader import get_dataset, detect_candidate_columns
from .cleaner import CLEANED_DATASET_STORE


def _resolve_column(df: pd.DataFrame, mapping: Dict[str, Any], canonical_key: str, fallback_candidates: List[str]) -> Optional[str]:
    """Find the column name in df matching canonical field or aliases."""
    # Check mapping first
    col = mapping.get(canonical_key)
    if not col and "optional" in mapping and isinstance(mapping["optional"], dict):
        col = mapping["optional"].get(canonical_key)
    
    if col and col in df.columns:
        return col

    # Check candidates
    col_lower = {c.lower().strip(): c for c in df.columns}
    for cand in fallback_candidates:
        if cand.lower().strip() in col_lower:
            return col_lower[cand.lower().strip()]
    return None


def compute_explorer_analytics(
    dataset_id: str,
    store_id: Optional[str] = None,
    category: Optional[str] = None,
    item_id: Optional[str] = None,
    series_id: Optional[str] = None,
    date_range: Optional[str] = "all",
) -> ExplorerResponse:
    """
    Execute full-dataset analytics with scope filtering and hierarchical dependencies.
    """
    entry = CLEANED_DATASET_STORE.get(dataset_id) or get_dataset(dataset_id)
    if not entry:
        raise ValueError(f"Dataset with ID '{dataset_id}' not found.")

    df: pd.DataFrame = entry["df"]
    mapping: Dict[str, Any] = entry.get("mapping") or detect_candidate_columns(list(df.columns))

    date_col = _resolve_column(df, mapping, "date", ["date", "datetime", "timestamp", "ds", "time"]) or df.columns[0]
    target_col = _resolve_column(df, mapping, "target", ["target", "sales", "demand", "units", "quantity", "val", "value"]) or df.columns[-1]
    series_col = _resolve_column(df, mapping, "series_id", ["series_id", "series", "id", "sku", "item_id"]) or df.columns[0]
    
    store_col = _resolve_column(df, mapping, "store_id", ["store_id", "store", "branch", "warehouse", "location"])
    cat_col = _resolve_column(df, mapping, "category", ["category", "dept_id", "cat_id", "department", "cat"])
    item_col = _resolve_column(df, mapping, "item_id", ["item_id", "item", "product_id", "product", "sku_id", "sku"])
    price_col = _resolve_column(df, mapping, "price", ["price", "sell_price", "unit_price", "selling_price"])

    has_store = bool(store_col and store_col in df.columns)
    has_category = bool(cat_col and cat_col in df.columns)
    has_item = bool(item_col and item_col in df.columns)
    has_series = bool(series_col and series_col in df.columns)
    has_price = bool(price_col and price_col in df.columns)

    # Hierarchical filter discovery across FULL dataset.
    # No auto-defaulting: when caller passes None, active_df uses the full dataset.
    # The af_* intermediates are only for available_filters cascade discovery.
    all_stores: List[str] = []
    if has_store:
        all_stores = sorted([str(x) for x in df[store_col].dropna().unique().tolist()])

    af_store_df = df
    if has_store and store_id and store_id in all_stores:
        af_store_df = df[df[store_col].astype(str) == str(store_id)]

    all_categories: List[str] = []
    if has_category:
        all_categories = sorted([str(x) for x in af_store_df[cat_col].dropna().unique().tolist()])

    af_cat_df = af_store_df
    if has_category and category and category in all_categories:
        af_cat_df = af_store_df[af_store_df[cat_col].astype(str) == str(category)]

    all_items: List[str] = []
    if has_item:
        all_items = sorted([str(x) for x in af_cat_df[item_col].dropna().unique().tolist()])

    af_item_df = af_cat_df
    if has_item and item_id and item_id in all_items:
        af_item_df = af_cat_df[af_cat_df[item_col].astype(str) == str(item_id)]

    all_series: List[str] = []
    if has_series:
        all_series = sorted([str(x) for x in af_item_df[series_col].dropna().unique().tolist()])

    # Apply ONLY explicitly-provided filters to active_df (no auto-defaulting)
    active_df = df.copy()
    if has_store and store_id:
        active_df = active_df[active_df[store_col].astype(str) == str(store_id)]
    if has_category and category:
        active_df = active_df[active_df[cat_col].astype(str) == str(category)]
    if has_item and item_id:
        active_df = active_df[active_df[item_col].astype(str) == str(item_id)]
    if has_series and series_id:
        active_df = active_df[active_df[series_col].astype(str) == str(series_id)]

    # Date range window filtering
    if date_range in ["30d", "90d", "180d"] and len(active_df) > 0 and date_col in active_df.columns:
        try:
            active_df[date_col] = pd.to_datetime(active_df[date_col])
            max_dt = active_df[date_col].max()
            days = 30 if date_range == "30d" else (90 if date_range == "90d" else 180)
            cutoff = max_dt - pd.Timedelta(days=days)
            active_df = active_df[active_df[date_col] >= cutoff]
        except Exception:
            pass

    # Ensure numeric target
    active_df[target_col] = pd.to_numeric(active_df[target_col], errors="coerce").fillna(0.0)

    # Summary KPIs over FULL active dataset
    total_rows = int(len(active_df))
    total_series = int(active_df[series_col].nunique()) if (has_series and total_rows > 0) else (1 if total_rows > 0 else 0)
    total_demand = round(float(active_df[target_col].sum()), 2) if total_rows > 0 else 0.0
    avg_daily_demand = round(float(active_df[target_col].mean()), 2) if total_rows > 0 else 0.0
    max_demand = round(float(active_df[target_col].max()), 2) if total_rows > 0 else 0.0
    min_demand = round(float(active_df[target_col].min()), 2) if total_rows > 0 else 0.0
    zero_days_count = int((active_df[target_col] == 0).sum()) if total_rows > 0 else 0
    zero_days_pct = round((zero_days_count / total_rows) * 100.0, 2) if total_rows > 0 else 0.0

    date_min = str(active_df[date_col].min())[:10] if total_rows > 0 else ""
    date_max = str(active_df[date_col].max())[:10] if total_rows > 0 else ""

    # Trend calculation over FULL dataset
    trend_points: List[ExplorerTrendPoint] = []
    if total_rows > 0:
        # Group by date and sum target (if multiple series in scope) or exact series value
        daily = active_df.groupby(date_col)[target_col].sum().reset_index()
        daily = daily.sort_values(by=date_col).reset_index(drop=True)
        # Compute 7-day rolling average
        rolling = daily[target_col].rolling(window=7, min_periods=1).mean()
        
        for i, row in daily.iterrows():
            d_str = str(row[date_col])[:10]
            val = round(float(row[target_col]), 2)
            r_val = round(float(rolling.iloc[i]), 2)
            trend_points.append(ExplorerTrendPoint(date=d_str, sales=val, rollingAvg=r_val))

    # Store breakdown over FULL dataset (all stores in dataset)
    store_breakdown: List[ExplorerBreakdownItem] = []
    if has_store:
        st_series = df.groupby(store_col)[target_col].sum().sort_values(ascending=False)
        max_val = float(st_series.max()) if len(st_series) > 0 and st_series.max() > 0 else 1.0
        for s_name, s_val in st_series.head(10).items():
            pct = round((float(s_val) / max_val) * 100.0)
            store_breakdown.append(ExplorerBreakdownItem(
                id=str(s_name),
                val=round(float(s_val), 2),
                pct=pct
            ))

    # Category breakdown over FULL dataset for the selected store (or all stores)
    category_breakdown: List[ExplorerBreakdownItem] = []
    if has_category:
        cat_base = af_store_df
        cat_series = cat_base.groupby(cat_col)[target_col].sum().sort_values(ascending=False)
        total_cat = float(cat_series.sum()) if len(cat_series) > 0 and cat_series.sum() > 0 else 1.0
        for c_name, c_val in cat_series.items():
            share_pct = (float(c_val) / total_cat) * 100.0
            category_breakdown.append(ExplorerBreakdownItem(
                name=str(c_name),
                count=round(float(c_val), 2),
                share=f"{share_pct:.1f}%"
            ))

    # Item breakdown over FULL dataset
    item_breakdown: List[ExplorerBreakdownItem] = []
    if has_item:
        item_base = af_cat_df if len(af_cat_df) > 0 else df
        item_series = item_base.groupby(item_col)[target_col].sum().sort_values(ascending=False).head(10)
        for i_name, i_val in item_series.items():
            item_breakdown.append(ExplorerBreakdownItem(
                name=str(i_name),
                val=round(float(i_val), 2)
            ))

    # Price statistics
    price_movement = None
    if has_price and total_rows > 0:
        prices = pd.to_numeric(active_df[price_col], errors="coerce").dropna()
        if len(prices) > 0:
            price_movement = {
                "current_price": round(float(prices.iloc[-1]), 2),
                "avg_price": round(float(prices.mean()), 2),
                "min_price": round(float(prices.min()), 2),
                "max_price": round(float(prices.max()), 2),
            }

    return ExplorerResponse(
        dataset_id=dataset_id,
        scope=ExplorerScope(
            dataset_id=dataset_id,
            store_id=store_id if has_store else None,
            category=category if has_category else None,
            item_id=item_id if has_item else None,
            series_id=series_id if has_series else None,
            date_range=date_range or "all",
        ),
        dimensions=ExplorerDimensions(
            has_store=has_store,
            has_category=has_category,
            has_item=has_item,
            has_series=has_series,
            has_price=has_price,
        ),
        available_filters=ExplorerAvailableFilters(
            stores=all_stores,
            categories=all_categories,
            items=all_items,
            series=all_series,
        ),
        total_rows=total_rows,
        total_series=total_series,
        total_demand=total_demand,
        avg_daily_demand=avg_daily_demand,
        max_demand=max_demand,
        min_demand=min_demand,
        zero_days_count=zero_days_count,
        zero_days_pct=zero_days_pct,
        date_min=date_min,
        date_max=date_max,
        trend=trend_points,
        store_breakdown=store_breakdown,
        category_breakdown=category_breakdown,
        item_breakdown=item_breakdown,
        price_movement=price_movement,
    )
