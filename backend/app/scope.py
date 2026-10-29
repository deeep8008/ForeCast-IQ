"""
Canonical ActiveScope helpers for ForecastIQ.

Every analytical artifact (explorer, forecast, evaluation, comparison,
insights, monitoring, MongoDB) must key off this exact scope tuple:

    dataset_id, store_id, category, item_id, series_id, model, horizon

Only dimensions that exist on the dataset are populated.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

import pandas as pd


SCOPE_FIELDS = (
    "dataset_id",
    "store_id",
    "category",
    "item_id",
    "series_id",
    "model",
    "horizon",
)

_INSUFFICIENT_RE = re.compile(
    r"(?:Series has|Available:?)\s*(\d+)\s*observations?.*?(?:requires at least|Required:?)\s*(\d+)",
    re.IGNORECASE | re.DOTALL,
)


def normalize_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text.lower() in {"all", "none", "null", "undefined"}:
        return None
    return text


def make_scope_key(
    dataset_id: str,
    store_id: Optional[str] = None,
    category: Optional[str] = None,
    item_id: Optional[str] = None,
    series_id: Optional[str] = None,
    model: Optional[str] = None,
    horizon: Optional[int] = None,
) -> str:
    parts = [
        f"ds:{dataset_id}",
        f"store:{normalize_optional(store_id) or '_'}",
        f"cat:{normalize_optional(category) or '_'}",
        f"item:{normalize_optional(item_id) or '_'}",
        f"series:{normalize_optional(series_id) or '_'}",
        f"model:{normalize_optional(model) or '_'}",
        f"h:{horizon if horizon is not None else '_'}",
    ]
    return "|".join(parts)


def build_scope_dict(
    dataset_id: str,
    store_id: Optional[str] = None,
    category: Optional[str] = None,
    item_id: Optional[str] = None,
    series_id: Optional[str] = None,
    model: Optional[str] = None,
    horizon: Optional[int] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    scope = {
        "dataset_id": dataset_id,
        "store_id": normalize_optional(store_id),
        "category": normalize_optional(category),
        "item_id": normalize_optional(item_id),
        "series_id": normalize_optional(series_id),
        "model": normalize_optional(model),
        "horizon": horizon,
        "scope_key": make_scope_key(dataset_id, store_id, category, item_id, series_id, model, horizon),
    }
    if extra:
        scope.update(extra)
    return scope


def resolve_dimension_columns(df: pd.DataFrame, mapping: Optional[Dict[str, Any]] = None) -> Dict[str, Optional[str]]:
    mapping = mapping or {}
    optional = mapping.get("optional") if isinstance(mapping.get("optional"), dict) else {}

    def pick(mapped: Optional[str], candidates: list) -> Optional[str]:
        if mapped and mapped in df.columns:
            return mapped
        for cand in candidates:
            if cand in df.columns:
                return cand
        return None

    return {
        "series_id": pick(mapping.get("series_id"), ["series_id"]),
        "date": pick(mapping.get("date"), ["date"]),
        "target": pick(mapping.get("target"), ["target"]),
        "store_id": pick(optional.get("store_id"), ["store_id", "store", "branch"]),
        "category": pick(optional.get("category"), ["category", "dept_id", "cat_id", "department"]),
        "item_id": pick(optional.get("item_id"), ["item_id", "item", "product_id", "product", "sku_id"]),
    }


def apply_scope_filters(
    df: pd.DataFrame,
    mapping: Optional[Dict[str, Any]] = None,
    store_id: Optional[str] = None,
    category: Optional[str] = None,
    item_id: Optional[str] = None,
    series_id: Optional[str] = None,
) -> Tuple[pd.DataFrame, Dict[str, Optional[str]]]:
    cols = resolve_dimension_columns(df, mapping)
    scoped = df.copy()
    store_id = normalize_optional(store_id)
    category = normalize_optional(category)
    item_id = normalize_optional(item_id)
    series_id = normalize_optional(series_id)

    if cols["store_id"] and store_id:
        scoped = scoped[scoped[cols["store_id"]].astype(str) == str(store_id)]
    if cols["category"] and category:
        scoped = scoped[scoped[cols["category"]].astype(str) == str(category)]
    if cols["item_id"] and item_id:
        scoped = scoped[scoped[cols["item_id"]].astype(str) == str(item_id)]
    if cols["series_id"] and series_id:
        scoped = scoped[scoped[cols["series_id"]].astype(str) == str(series_id)]
    return scoped, cols


def resolve_series_id(
    df: pd.DataFrame,
    mapping: Optional[Dict[str, Any]] = None,
    series_id: Optional[str] = None,
    store_id: Optional[str] = None,
    category: Optional[str] = None,
    item_id: Optional[str] = None,
) -> str:
    scoped, cols = apply_scope_filters(
        df,
        mapping=mapping,
        store_id=store_id,
        category=category,
        item_id=item_id,
        series_id=series_id,
    )
    series_col = cols["series_id"]
    if series_col is None or series_col not in scoped.columns:
        # If dataset is clean single-series, return default_series
        if "series_id" in scoped.columns:
            return str(scoped["series_id"].iloc[0])
        return "default_series"
    if series_id and not scoped.empty:
        return str(series_id)
    if series_id:
        raise ValueError(f"Series '{series_id}' not found in dataset.")
    if scoped.empty:
        raise ValueError("No observations match the selected analytical scope.")
    return str(scoped[series_col].astype(str).iloc[0])


def extract_scope_values_from_frame(
    series_df: pd.DataFrame,
    mapping: Optional[Dict[str, Any]] = None,
    store_id: Optional[str] = None,
    category: Optional[str] = None,
    item_id: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    cols = resolve_dimension_columns(series_df, mapping)

    def first(col_name: Optional[str], fallback: Optional[str]) -> Optional[str]:
        if fallback:
            return normalize_optional(fallback)
        if col_name and col_name in series_df.columns and not series_df.empty:
            return normalize_optional(str(series_df[col_name].iloc[0]))
        return None

    return {
        "store_id": first(cols["store_id"], store_id),
        "category": first(cols["category"], category),
        "item_id": first(cols["item_id"], item_id),
    }


def user_friendly_insufficient_history(exc: Exception) -> Optional[Dict[str, Any]]:
    text = str(exc)
    match = _INSUFFICIENT_RE.search(text)
    if "insufficient" not in text.lower() and match is None:
        return None
    available = int(match.group(1)) if match else None
    required = int(match.group(2)) if match else None
    return {
        "message": "Not enough historical data for this forecast horizon.",
        "available": available,
        "required": required,
        "debug": text,
    }
