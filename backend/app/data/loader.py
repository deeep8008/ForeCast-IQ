"""
Safe Data Loader and In-Memory Storage
ForecastIQ Backend
"""
import io
import uuid
from typing import Dict, Any, Optional, Tuple, List
import pandas as pd
from .schema import MANDATORY_CANONICAL_FIELDS, OPTIONAL_CANONICAL_FIELDS

# In-memory session store (no MongoDB required in Phase 2)
DATASET_STORE: Dict[str, Dict[str, Any]] = {}


def detect_candidate_columns(columns: List[str]) -> Dict[str, Any]:
    """
    Intelligently map user columns to canonical schema fields using
    case-insensitive matching and standard alias heuristics.
    """
    col_lower = {col.lower().strip(): col for col in columns}

    def match_alias(aliases: List[str]) -> Optional[str]:
        # 1. Exact match
        for alias in aliases:
            if alias.lower() in col_lower:
                return col_lower[alias.lower()]
        # 2. Normalized match (remove underscores, spaces, hyphens)
        clean_cols = {col.lower().replace("_", "").replace(" ", "").replace("-", ""): col for col in columns}
        for alias in aliases:
            clean_alias = alias.lower().replace("_", "").replace(" ", "").replace("-", "")
            if clean_alias in clean_cols:
                return clean_cols[clean_alias]
        # 3. Suffix or substring match for compound column names (e.g. Weekly_Sales, order_date)
        for col_clean, original in col_lower.items():
            for alias in aliases:
                a_clean = alias.lower().strip()
                if len(a_clean) >= 4 and (
                    col_clean.endswith(f"_{a_clean}")
                    or col_clean.startswith(f"{a_clean}_")
                    or f"_{a_clean}_" in col_clean
                    or a_clean in col_clean.split("_")
                ):
                    return original
        return None

    # Mandatory
    date_col = match_alias([
        "date", "datetime", "timestamp", "ds", "time", "d", "month", "observation_date",
        "order_date", "transaction_date", "period", "week", "day", "year"
    ])
    series_col = match_alias([
        "series_id", "series", "store_item", "store_dept", "unique_id", "ts_id", "seriesid"
    ])
    target_col = match_alias([
        "weekly_sales", "monthly_sales", "daily_sales", "total_sales", "store_sales",
        "sales", "target", "demand", "units", "unit_sales", "quantity", "val", "value",
        "revenue", "volume", "turnover", "qty", "amount", "count", "transactions",
        "passengers", "#passengers", "pjme_mw", "mw", "load", "power", "y"
    ])

    # Optional canonical
    optional_mapped: Dict[str, str] = {}
    for opt_field in OPTIONAL_CANONICAL_FIELDS:
        if opt_field == "store_id":
            matched = match_alias(["store_id", "store", "branch", "warehouse", "location"])
        elif opt_field == "item_id":
            matched = match_alias(["item_id", "item", "product_id", "product", "sku_id", "sku"])
        elif opt_field == "category":
            matched = match_alias(["category", "dept", "department", "cat", "product_category"])
        elif opt_field == "company":
            matched = match_alias(["company", "org", "enterprise", "business_unit"])
        elif opt_field == "region":
            matched = match_alias(["region", "district", "zone", "area", "market"])
        elif opt_field == "state":
            matched = match_alias(["state", "province", "territory"])
        elif opt_field == "price":
            matched = match_alias(["price", "sell_price", "unit_price", "selling_price", "base_price"])
        elif opt_field == "promotion":
            matched = match_alias(["promotion", "promo", "discount", "is_promo", "event", "deal"])
        elif opt_field == "holiday":
            matched = match_alias(["holiday", "event_name", "is_holiday", "holiday_name"])
        elif opt_field == "weather":
            matched = match_alias(["weather", "temperature", "temp", "precipitation", "rain"])
        elif opt_field == "customer_segment":
            matched = match_alias(["customer_segment", "segment", "channel", "customer_type"])
        else:
            matched = None

        if matched and matched != date_col and matched != series_col and matched != target_col:
            optional_mapped[opt_field] = matched

    # Find other unassigned columns
    all_assigned = {date_col, series_col, target_col, *optional_mapped.values()}
    for col in columns:
        if col not in all_assigned:
            optional_mapped[f"feature_{col}"] = col

    # Identify candidate entity identification columns (strictly excluding explanatory features)
    candidate_entities: List[str] = []
    # Known entity-identifying dimensions
    entity_keywords = [
        "store_id", "store", "item_id", "item", "product_id", "product", "sku_id", "sku",
        "branch", "warehouse", "location", "category", "dept", "department", "cat",
        "company", "org", "enterprise", "business_unit", "region", "district", "zone",
        "market", "state", "province", "territory", "machine_id", "machine", "building_id", "building",
        "device_id", "device", "station_id", "station", "meter_id", "meter"
    ]
    # Covariates to strictly exclude from entity grouping
    covariate_exclusions = {
        "price", "sell_price", "unit_price", "selling_price", "base_price",
        "promotion", "promo", "discount", "is_promo", "event", "deal",
        "holiday", "event_name", "is_holiday", "holiday_name",
        "weather", "temperature", "temp", "precipitation", "rain",
        "target", "sales", "demand", "units", "y", "quantity", "val", "value", "revenue",
        "date", "datetime", "timestamp", "ds", "time", "d", "observation_date", "month"
    }

    for col in columns:
        clow = col.lower().strip()
        if clow in covariate_exclusions:
            continue
        if col in [date_col, target_col]:
            continue
        if col == series_col:
            continue
        if any(ek in clow for ek in entity_keywords):
            candidate_entities.append(col)

    # If series_col was not explicitly found in columns, resolve from candidate_entities
    composite_keys: List[str] = []
    if not series_col:
        if len(candidate_entities) > 1:
            composite_keys = list(candidate_entities)
            series_col = ""
        elif len(candidate_entities) == 1:
            series_col = candidate_entities[0]
        elif "series_id" in col_lower:
            series_col = col_lower["series_id"]

    # Final fallback for target_col if unassigned
    if not target_col:
        for col in columns:
            clow = col.lower().strip()
            if clow not in covariate_exclusions and col != date_col and col != series_col and col not in candidate_entities:
                if any(m in clow for m in ["sales", "demand", "target", "revenue", "units", "volume"]):
                    target_col = col
                    break

    return {
        "date": date_col or "",
        "series_id": series_col or "",
        "target": target_col or "",
        "candidate_entity_columns": candidate_entities,
        "composite_series_keys": composite_keys,
        "optional": optional_mapped,
    }


def load_csv_from_bytes(file_bytes: bytes, filename: str) -> Tuple[str, pd.DataFrame]:
    """
    Safely parse CSV from in-memory bytes, trying UTF-8 and fallback encodings.
    """
    dataset_id = str(uuid.uuid4())
    
    # Try UTF-8 first, fallback to latin-1
    try:
        df = pd.read_csv(io.BytesIO(file_bytes), encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(io.BytesIO(file_bytes), encoding="latin-1")
    except Exception as e:
        raise ValueError(f"Failed to read CSV: {str(e)}")

    if df.empty and len(df.columns) == 0:
        raise ValueError("Uploaded CSV is completely empty.")

    # Clean whitespace in column headers
    df.columns = [str(c).strip() for c in df.columns]

    save_dataset(dataset_id, df, filename, metadata={"original_columns": list(df.columns)})
    return dataset_id, df


def save_dataset(dataset_id: str, df: pd.DataFrame, filename: str, metadata: Optional[Dict[str, Any]] = None, mapping: Optional[Dict[str, Any]] = None) -> None:
    """Store dataset in in-memory session cache and persist metadata and data to MongoDB."""
    meta = metadata or {}
    meta["rows"] = len(df)
    meta["columns"] = list(df.columns)
    meta["filename"] = filename
    if mapping:
        meta["mapping"] = mapping

    DATASET_STORE[dataset_id] = {
        "df": df,
        "filename": filename,
        "metadata": meta,
        "mapping": mapping or meta.get("mapping"),
    }

    try:
        from ..db.mongo import MongoRepository
        csv_text = df.to_csv(index=False)
        saved = MongoRepository.save_dataset_record(dataset_id, meta, csv_text)
        if not saved:
            logger.warning(f"MongoRepository.save_dataset_record returned False for dataset_id={dataset_id}")
    except Exception as ex:
        logger.warning(f"Failed to persist dataset record to MongoDB for dataset_id={dataset_id}: {ex}")


def get_dataset(dataset_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve stored dataset from in-memory cache, or automatically restore
    from MongoDB persistence if the in-memory cache is empty (e.g. after backend restart).
    """
    if dataset_id in DATASET_STORE:
        return DATASET_STORE[dataset_id]

    try:
        from ..db.mongo import MongoRepository
        record = MongoRepository.get_dataset_record(dataset_id)
        if record:
            meta, csv_content = record
            if csv_content:
                df = pd.read_csv(io.StringIO(csv_content))
                filename = meta.get("filename", "restored_dataset.csv")
                entry = {
                    "df": df,
                    "filename": filename,
                    "metadata": meta,
                    "mapping": meta.get("mapping"),
                }
                DATASET_STORE[dataset_id] = entry
                return entry
    except Exception:
        pass

    return None
