"""
API Endpoints for Universal Dataset Ingestion & Profiling
ForecastIQ Backend
"""
import io
import os
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from ..data.schema import (
    UploadResponse,
    DatasetProfile,
    ValidationReport,
    ReadinessReport,
    ColumnFeatureProfile,
    ColumnMapping,
    ReadinessStatus,
    CleaningReport,
    SeriesQualityAnalysisReport,
    SplitReport,
    CleanDatasetRequest,
    PipelineStatus,
    ForecastResult,
    ForecastRequest,
    ArimaConfig,
    SarimaConfig,
    ProphetConfig,
    BacktestRequest,
    EvaluationSummaryResponse,
    BusinessInsightsResponse,
    InsightRequest,
    MonitoringReport,
    ExplorerResponse,
)
from ..models.arima import ArimaForecaster
from ..models.sarima import SarimaForecaster
from ..models.prophet_model import ProphetForecaster
from ..models.lightgbm import LightgbmForecaster
from ..models.deepar import DeeparForecaster
from ..models.tft import TftForecaster
from ..models.config import ModelDefaults
from ..evaluation.backtesting import BacktestingEngine
from ..insights.business_insights import BusinessInsightEngine
from ..insights.monitoring import MonitoringTracker

from ..data.loader import load_csv_from_bytes, get_dataset, detect_candidate_columns, save_dataset
from ..data.profiler import profile_dataset
from ..data.validator import validate_schema_and_series
from ..features.analyzer import analyze_features
from ..data.cleaner import (
    evaluate_dataset_readiness,
    clean_canonical_dataset,
    analyze_series_quality,
    compute_chronological_splits,
    CLEANED_DATASET_STORE,
)
from ..features.engineer import (
    engineer_time_series_features,
    prepare_arima_dataset,
    prepare_prophet_dataset,
    prepare_lightgbm_dataset,
    prepare_darts_dataset,
)
from ..data.adapters.m5_adapter import M5Adapter
from ..scope import user_friendly_insufficient_history, build_scope_dict
import pandas as pd


router = APIRouter()


def _raise_forecast_http(exc: Exception) -> None:
    friendly = user_friendly_insufficient_history(exc)
    if friendly:
        raise HTTPException(status_code=400, detail=friendly)
    raise HTTPException(status_code=400, detail=str(exc))


@router.get("/health")
def health_check():
    """Service health and readiness check with database status reporting."""
    from ..db.mongo import MongoManager
    from ..config.settings import settings

    mongo_connected = MongoManager.is_connected()
    return {
        "status": "healthy",
        "service": "ForecastIQ Universal Dataset Engine",
        "version": "1.0.0",
        "database": {
            "type": "mongodb",
            "enabled": settings.MONGODB_ENABLED,
            "connected": mongo_connected,
            "database_name": settings.MONGODB_DATABASE if mongo_connected else None
        }
    }


@router.get("/db/status")
def database_status():
    """Report detailed status of MongoDB persistence layer."""
    from ..db.mongo import MongoManager
    from ..config.settings import settings

    is_conn = MongoManager.is_connected()
    return {
        "mongodb_enabled": settings.MONGODB_ENABLED,
        "connected": is_conn,
        "database_name": settings.MONGODB_DATABASE,
        "status": "ONLINE" if is_conn else "OFFLINE / IN-MEMORY FALLBACK",
        "persistence_mode": "MONGODB_PERSISTENT" if is_conn else "LOCAL_MEMORY_FALLBACK"
    }


@router.get("/db/health")
def database_health():
    """Dedicated MongoDB health check endpoint verifying ping and read/write availability."""
    from ..db.mongo import MongoManager
    from ..config.settings import settings

    if not settings.MONGODB_ENABLED:
        return {
            "status": "disabled",
            "connected": False,
            "message": "MongoDB is disabled in configuration"
        }

    db = MongoManager.get_db()
    if db is None:
        return {
            "status": "unhealthy",
            "connected": False,
            "message": "MongoDB connection could not be established"
        }

    try:
        # Perform live ping command on the active cluster
        ping_res = MongoManager._client.admin.command('ping')
        return {
            "status": "healthy",
            "connected": True,
            "database": settings.MONGODB_DATABASE,
            "ping": bool(ping_res.get("ok")),
            "message": "MongoDB Atlas connection is healthy and responsive"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "connected": False,
            "error": "MongoDB ping command failed",
            "detail": str(e)
        }


@router.post("/data/upload", response_model=UploadResponse)
async def upload_dataset(
    file: UploadFile = File(...),
):
    """
    Upload and profile an enterprise time-series CSV.
    Validates CSV type, parses data into canonical internal representation,
    and returns initial profiling and auto-detected column mappings.
    """
    filename = file.filename or "dataset.csv"
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Invalid file format. Please upload a standard CSV file (.csv).")

    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        dataset_id, df = load_csv_from_bytes(content, filename)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process CSV: {str(e)}")

    # Detect candidate mapping
    initial_mapping = detect_candidate_columns(list(df.columns))
    
    # Store initial mapping in DATASET_STORE and pre-clean
    from ..data.loader import DATASET_STORE
    if dataset_id in DATASET_STORE:
        DATASET_STORE[dataset_id]["mapping"] = initial_mapping
    try:
        clean_canonical_dataset(dataset_id, df, initial_mapping)
    except Exception:
        pass

    # Run validation to determine status
    val_report, _ = validate_schema_and_series(dataset_id, df, initial_mapping)

    summary_msg = (
        f"Successfully ingested {len(df):,} rows and {len(df.columns)} columns from '{filename}'. "
        f"Status: {val_report.status.value}."
    )

    return UploadResponse(
        dataset_id=dataset_id,
        filename=filename,
        rows=int(len(df)),
        columns=int(len(df.columns)),
        status=val_report.status,
        detected_mapping=ColumnMapping(
            date=initial_mapping.get("date", ""),
            series_id=initial_mapping.get("series_id", ""),
            target=initial_mapping.get("target", ""),
            optional=initial_mapping.get("optional", {})
        ),
        summary=summary_msg,
    )


@router.get("/data/{dataset_id}/profile", response_model=DatasetProfile)
def get_dataset_profile(dataset_id: str):
    """Get statistical profile for an uploaded dataset."""
    entry = get_dataset(dataset_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Dataset with ID '{dataset_id}' not found.")

    df = entry["df"]
    filename = entry["filename"]
    mapping = detect_candidate_columns(list(df.columns))
    return profile_dataset(dataset_id, df, filename, mapping)


@router.get("/data/{dataset_id}/validation", response_model=ValidationReport)
def get_dataset_validation(dataset_id: str):
    """Get schema and series validation report."""
    entry = get_dataset(dataset_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Dataset with ID '{dataset_id}' not found.")

    df = entry["df"]
    mapping = detect_candidate_columns(list(df.columns))
    val_report, _ = validate_schema_and_series(dataset_id, df, mapping)
    return val_report


@router.get("/data/{dataset_id}/features")
def get_dataset_features(dataset_id: str):
    """Get column classifications and leakage diagnostics."""
    entry = get_dataset(dataset_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Dataset with ID '{dataset_id}' not found.")

    df = entry["df"]
    mapping = detect_candidate_columns(list(df.columns))
    return analyze_features(df, mapping)


@router.get("/data/{dataset_id}/preview")
def get_dataset_preview(dataset_id: str, limit: int = 5):
    """Get preview rows of dataset."""
    entry = get_dataset(dataset_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Dataset with ID '{dataset_id}' not found.")

    df = entry["df"]
    preview_df = df.head(limit).fillna("")
    return {
        "headers": list(df.columns),
        "rows": preview_df.to_dict(orient="records")
    }


@router.get("/data/{dataset_id}/explorer", response_model=ExplorerResponse)
def get_dataset_explorer_analytics(
    dataset_id: str,
    store_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    item_id: Optional[str] = Query(None),
    series_id: Optional[str] = Query(None),
    date_range: Optional[str] = Query("all"),
):
    """
    Calculate comprehensive descriptive analytics and historical trends
    from the COMPLETE active dataset (never preview rows).
    """
    from ..data.explorer import compute_explorer_analytics
    try:
        return compute_explorer_analytics(
            dataset_id=dataset_id,
            store_id=store_id,
            category=category,
            item_id=item_id,
            series_id=series_id,
            date_range=date_range,
        )
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Data explorer analytics failed: {str(e)}")


@router.get("/data/{dataset_id}/readiness", response_model=ReadinessReport)
def get_dataset_readiness(
    dataset_id: str,
    date_col: Optional[str] = None,
    series_col: Optional[str] = None,
    target_col: Optional[str] = None,
):
    """
    Get comprehensive readiness report for multi-horizon forecasting,
    allowing optional manual column mapping overrides.
    """
    entry = get_dataset(dataset_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Dataset with ID '{dataset_id}' not found.")

    df = entry["df"]
    filename = entry["filename"]
    mapping = detect_candidate_columns(list(df.columns))

    if date_col:
        mapping["date"] = date_col
    if series_col:
        mapping["series_id"] = series_col
    if target_col:
        mapping["target"] = target_col

    return evaluate_dataset_readiness(dataset_id, df, filename, mapping)


@router.post("/data/{dataset_id}/remap", response_model=ReadinessReport)
def remap_dataset_columns(
    dataset_id: str,
    mapping: ColumnMapping,
):
    """
    Update column mappings and immediately re-evaluate validation and readiness.
    """
    entry = get_dataset(dataset_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Dataset with ID '{dataset_id}' not found.")

    df = entry["df"]
    filename = entry["filename"]
    
    mapping_dict = {
        "date": mapping.date,
        "series_id": mapping.series_id,
        "target": mapping.target,
        "composite_series_keys": mapping.composite_series_keys or [],
        "candidate_entity_columns": mapping.candidate_entity_columns or [],
        "optional": mapping.optional
    }

    # Persist the remapped columns in dataset store and re-clean
    entry["mapping"] = mapping_dict
    from ..data.loader import DATASET_STORE
    if dataset_id in DATASET_STORE:
        DATASET_STORE[dataset_id]["mapping"] = mapping_dict

    try:
        clean_canonical_dataset(dataset_id, df, mapping_dict)
    except Exception:
        pass

    return evaluate_dataset_readiness(dataset_id, df, filename, mapping_dict)


@router.post("/data/m5/convert", response_model=UploadResponse)
def convert_m5_sample(
    max_series: int = Query(5, ge=1, le=50),
    max_days: int = Query(194, ge=14, le=1941)
):
    """
    Convert sample of local M5 dataset into canonical schema using M5Adapter.
    """
    project_root = Path(__file__).resolve().parents[3]
    dataset_dir = project_root / "Dataset"
    sales_file = dataset_dir / "sales_train_validation.csv"
    cal_file = dataset_dir / "calendar.csv"
    prices_file = dataset_dir / "sell_prices.csv"

    if not os.path.exists(sales_file):
        raise HTTPException(status_code=404, detail="M5 dataset files not found on server.")

    try:
        # Load across multiple stores so CA_1, CA_2 etc. can be verified
        sales_head = pd.read_csv(sales_file, nrows=7000)
        # Sample evenly across available stores
        stores_found = sales_head["store_id"].unique().tolist()
        per_store = max(1, max_series // max(1, len(stores_found)))
        sampled_dfs = []
        for s in stores_found:
            sampled_dfs.append(sales_head[sales_head["store_id"] == s].head(per_store))
        sales_df = pd.concat(sampled_dfs, ignore_index=True).head(max_series)
        if len(sales_df) == 0:
            sales_df = sales_head.head(max_series)
        cal_df = pd.read_csv(cal_file) if os.path.exists(cal_file) else None

        # Load prices only for the stores/items that appear in the sampled sales data.
        # sell_prices.csv is sorted by store so CA_2/CA_3 don't appear in the first 2000 rows.
        # Read in chunks and filter; this avoids loading the full ~6M-row file into memory.
        prices_df = None
        if os.path.exists(prices_file):
            needed_stores = set(sales_df["store_id"].unique())
            needed_items = set(sales_df["item_id"].unique()) if "item_id" in sales_df.columns else None
            price_chunks = []
            for chunk in pd.read_csv(prices_file, chunksize=50_000):
                mask = chunk["store_id"].isin(needed_stores)
                if needed_items is not None:
                    mask = mask & chunk["item_id"].isin(needed_items)
                filtered = chunk[mask]
                if not filtered.empty:
                    price_chunks.append(filtered)
                # Stop early if all needed stores are fully covered
                if price_chunks:
                    found = set(pd.concat(price_chunks)["store_id"].unique())
                    if found >= needed_stores:
                        break
            prices_df = pd.concat(price_chunks, ignore_index=True) if price_chunks else None

        canonical_df = M5Adapter.transform_sales_wide_to_canonical(
            sales_df=sales_df,
            calendar_df=cal_df,
            prices_df=prices_df,
            max_series=max_series,
            max_days=max_days
        )

        dataset_id, _ = load_csv_from_bytes(
            canonical_df.to_csv(index=False).encode("utf-8"),
            filename="m5_canonical_sample.csv"
        )

        mapping = detect_candidate_columns(list(canonical_df.columns))

        return UploadResponse(
            dataset_id=dataset_id,
            filename="m5_canonical_sample.csv",
            rows=int(len(canonical_df)),
            columns=int(len(canonical_df.columns)),
            status=ReadinessStatus.READY,
            detected_mapping=ColumnMapping(
                date=mapping["date"],
                series_id=mapping["series_id"],
                target=mapping["target"],
                optional=mapping.get("optional", {})
            ),
            summary=f"Converted {max_series} M5 series over {max_days} days to canonical universal schema."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to convert M5 data: {str(e)}")


@router.post("/data/{dataset_id}/clean", response_model=CleaningReport)
def clean_dataset(
    dataset_id: str,
    req: Optional[CleanDatasetRequest] = None,
):
    """
    Execute real Phase 3 cleaning pipeline:
    - Exact duplicate removal
    - Deterministic conflict resolution (SUM for additive target, first/max for covariates)
    - Zero target preservation & missing target audit
    - Negative target review
    - Date gaps audit
    - Contextual vs abnormal outlier detection
    """
    entry = get_dataset(dataset_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Dataset with ID '{dataset_id}' not found.")

    df = entry["df"]
    mapping = detect_candidate_columns(list(df.columns))
    if req and req.series_id:
        mapping["series_id"] = req.series_id
    if req and req.composite_series_keys:
        mapping["composite_series_keys"] = req.composite_series_keys

    additive = req.additive_aggregation if req else True
    target_type = req.target_type if req and req.target_type else "additive"
    impute = req.impute_optional_features if req else True

    _, report = clean_canonical_dataset(
        dataset_id=dataset_id,
        df=df,
        mapping=mapping,
        additive_aggregation=additive,
        target_type=target_type,
        impute_optional_features=impute,
    )
    return report


@router.get("/data/{dataset_id}/cleaning-report", response_model=CleaningReport)
def get_cleaning_report(dataset_id: str):
    """Get the latest cleaning report for a dataset."""
    if dataset_id in CLEANED_DATASET_STORE:
        return CLEANED_DATASET_STORE[dataset_id]["report"]

    # If not yet explicitly cleaned, run default clean
    entry = get_dataset(dataset_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Dataset with ID '{dataset_id}' not found.")

    df = entry["df"]
    mapping = detect_candidate_columns(list(df.columns))
    _, report = clean_canonical_dataset(dataset_id, df, mapping)
    return report


@router.get("/data/{dataset_id}/series-quality", response_model=SeriesQualityAnalysisReport)
def get_series_quality_report(dataset_id: str):
    """Get series-level granular quality metrics and multi-horizon feasibility."""
    entry = CLEANED_DATASET_STORE.get(dataset_id) or get_dataset(dataset_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Dataset with ID '{dataset_id}' not found.")

    df = entry["df"]
    mapping = detect_candidate_columns(list(df.columns))
    return analyze_series_quality(dataset_id, df, mapping)


@router.get("/data/{dataset_id}/splits", response_model=SplitReport)
def get_chronological_splits(
    dataset_id: str,
    test_horizon: Optional[int] = Query(None, ge=1, le=180),
    val_horizon: Optional[int] = Query(None, ge=1, le=180),
    strategy: Optional[str] = Query(None),
):
    """Get strictly chronological Train / Validation / Test temporal cutoffs on cleaned, model-eligible data."""
    if dataset_id not in CLEANED_DATASET_STORE:
        raw_entry = get_dataset(dataset_id)
        if not raw_entry:
            raise HTTPException(status_code=404, detail=f"Dataset with ID '{dataset_id}' not found.")
        mapping = detect_candidate_columns(list(raw_entry["df"].columns))
        clean_canonical_dataset(dataset_id, raw_entry["df"], mapping)

    entry = CLEANED_DATASET_STORE.get(dataset_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Dataset with ID '{dataset_id}' not found.")

    df = entry["df"]
    mapping = entry.get("mapping") or detect_candidate_columns(list(df.columns))
    # If explicit horizons are passed without strategy="80:20", use explicit horizons
    use_80_20 = (strategy == "80:20") or (test_horizon is None and val_horizon is None)
    return compute_chronological_splits(
        dataset_id,
        df,
        mapping,
        test_horizon_days=None if use_80_20 else test_horizon,
        val_horizon_days=None if use_80_20 else val_horizon,
        use_80_20_ratio=use_80_20
    )


@router.get("/data/{dataset_id}/preprocessing-status")
def get_preprocessing_status(dataset_id: str):
    """
    Get human-readable pipeline status:
    ANALYZING, CLEANING, NEEDS ATTENTION, or READY FOR MODEL TRAINING.
    """
    if dataset_id in CLEANED_DATASET_STORE:
        rep = CLEANED_DATASET_STORE[dataset_id]["report"]
        return {
            "dataset_id": dataset_id,
            "status": rep.pipeline_status.value,
            "cleaned_rows": rep.cleaned_rows,
            "unresolved_conflicts": rep.unresolved_conflicts,
            "is_ready_for_training": rep.pipeline_status == PipelineStatus.READY_FOR_MODEL_TRAINING,
        }

    entry = get_dataset(dataset_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Dataset with ID '{dataset_id}' not found.")

    return {
        "dataset_id": dataset_id,
        "status": PipelineStatus.ANALYZING.value,
        "cleaned_rows": len(entry["df"]),
        "unresolved_conflicts": 0,
        "is_ready_for_training": False,
    }


@router.get("/data/{dataset_id}/engineered-features")
def get_engineered_features_preview(dataset_id: str, limit: int = 5):
    """Preview lag, rolling, and calendar engineered features."""
    entry = CLEANED_DATASET_STORE.get(dataset_id) or get_dataset(dataset_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Dataset with ID '{dataset_id}' not found.")

    df = entry["df"]
    mapping = detect_candidate_columns(list(df.columns))
    feat_df = engineer_time_series_features(df, mapping)
    preview = feat_df.head(limit).fillna("").to_dict(orient="records")

    return {
        "dataset_id": dataset_id,
        "feature_columns": list(feat_df.columns),
        "preview_rows": preview,
    }


def _get_series_training_data(
    dataset_id: str,
    series_id: str
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Helper to retrieve and validate single series from cleaned store or raw dataset."""
    entry = CLEANED_DATASET_STORE.get(dataset_id) or get_dataset(dataset_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Dataset with ID '{dataset_id}' not found.")

    df = entry["df"].copy()
    mapping = entry.get("mapping") or detect_candidate_columns(list(df.columns))

    series_col = mapping.get("series_id") or "series_id"
    date_col = mapping.get("date") or "date"
    target_col = mapping.get("target") or "target"
    composite_keys = mapping.get("composite_series_keys") or []

    # 1. Composite series keys support
    if composite_keys and all(ck in df.columns for ck in composite_keys) and series_col not in df.columns:
        df["series_id"] = df[composite_keys].astype(str).agg("__".join, axis=1)
        series_col = "series_id"
    # 2. Check if series_col is valid and in df
    elif series_col not in df.columns:
        # Check if series_id requested matches values in any non-date/target column (e.g. store, item, etc.)
        matched_col = None
        for col in df.columns:
            if col not in [date_col, target_col]:
                unique_vals = [str(x) for x in df[col].dropna().unique()[:100]]
                if str(series_id) in unique_vals:
                    matched_col = col
                    break
        if matched_col:
            series_col = matched_col
        elif "series_id" in df.columns:
            series_col = "series_id"
        elif "default_series" in df.columns:
            series_col = "default_series"
        else:
            # Single-series dataset fallback: create default series
            df["series_id"] = "default_series"
            series_col = "series_id"

    # Filter to requested series
    series_df = df[df[series_col].astype(str) == str(series_id)].copy()
    if series_df.empty:
        # If single series dataset or series_id is default_series / all / empty
        if str(series_id) in ["default_series", "all", "None", "", "1"] and (len(df[series_col].unique()) == 1 or series_col == "series_id"):
            series_df = df.copy()
        elif str(series_id) in ["default_series", "all"]:
            series_df = df.copy()
        else:
            available_series = list(df[series_col].astype(str).unique()[:5])
            raise HTTPException(
                status_code=404,
                detail=f"Series '{series_id}' not found. Available series sample: {available_series}"
            )

    return series_df, mapping


def _persist_forecast(result: ForecastResult):
    """Persist forecast result to MongoDB if enabled, with error handling."""
    try:
        from ..db.mongo import MongoRepository
        saved = MongoRepository.save_forecast_result(result.model_dump())
        if not saved:
            logger.warning(f"Failed to persist forecast result for dataset={result.dataset_id}, series={result.series_id}")
    except Exception as ex:
        logger.warning(f"Error persisting forecast to MongoDB: {ex}")


@router.post("/forecast/arima", response_model=ForecastResult)
def generate_arima_forecast(
    dataset_id: str = Query(...),
    series_id: str = Query(...),
    horizon: int = Query(28, ge=7, le=90),
    p: int = Query(1, ge=0, le=5),
    d: int = Query(1, ge=0, le=2),
    q: int = Query(1, ge=0, le=5),
):
    """
    Fit and generate real out-of-sample forecast using statsmodels ARIMA.
    """
    series_df, mapping = _get_series_training_data(dataset_id, series_id)
    time_col = mapping.get("date", "date")
    target_col = mapping.get("target", "target")

    forecaster = ArimaForecaster(p=p, d=d, q=q)
    try:
        forecaster.fit(series_df, time_col=time_col, target_col=target_col, horizon=horizon)
        result = forecaster.forecast(horizon=horizon, dataset_id=dataset_id, series_id=series_id)
        _persist_forecast(result)
        return result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ARIMA forecast execution error: {str(e)}")


@router.post("/forecast/sarima", response_model=ForecastResult)
def generate_sarima_forecast(
    dataset_id: str = Query(...),
    series_id: str = Query(...),
    horizon: int = Query(28, ge=7, le=90),
    p: int = Query(1, ge=0, le=3),
    d: int = Query(1, ge=0, le=2),
    q: int = Query(1, ge=0, le=3),
    P: int = Query(1, ge=0, le=2),
    D: int = Query(0, ge=0, le=1),
    Q: int = Query(1, ge=0, le=2),
    seasonal_period: int = Query(7, ge=2, le=365),
):
    """
    Fit and generate real out-of-sample forecast using statsmodels SARIMA.
    """
    series_df, mapping = _get_series_training_data(dataset_id, series_id)
    time_col = mapping.get("date", "date")
    target_col = mapping.get("target", "target")

    forecaster = SarimaForecaster(
        order=(p, d, q),
        seasonal_order=(P, D, Q, seasonal_period)
    )
    try:
        forecaster.fit(series_df, time_col=time_col, target_col=target_col, horizon=horizon)
        result = forecaster.forecast(horizon=horizon, dataset_id=dataset_id, series_id=series_id)
        _persist_forecast(result)
        return result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SARIMA forecast execution error: {str(e)}")


@router.post("/forecast/prophet", response_model=ForecastResult)
def generate_prophet_forecast(
    dataset_id: str = Query(...),
    series_id: str = Query(...),
    horizon: int = Query(28, ge=7, le=90),
    weekly_seasonality: bool = Query(True),
    yearly_seasonality: bool = Query(False),
):
    """
    Fit and generate real out-of-sample forecast using Meta Prophet.
    """
    series_df, mapping = _get_series_training_data(dataset_id, series_id)
    time_col = mapping.get("date", "date")
    target_col = mapping.get("target", "target")

    forecaster = ProphetForecaster(
        weekly_seasonality=weekly_seasonality,
        yearly_seasonality=yearly_seasonality,
    )
    try:
        forecaster.fit(series_df, time_col=time_col, target_col=target_col, horizon=horizon)
        result = forecaster.forecast(horizon=horizon, dataset_id=dataset_id, series_id=series_id)
        _persist_forecast(result)
        return result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prophet forecast execution error: {str(e)}")


@router.post("/forecast/lightgbm", response_model=ForecastResult)
def generate_lightgbm_forecast(
    dataset_id: str = Query(...),
    series_id: str = Query(...),
    horizon: int = Query(28, ge=7, le=90),
    n_estimators: int = Query(100, ge=10, le=500),
    learning_rate: float = Query(0.05, ge=0.001, le=1.0),
    num_leaves: int = Query(31, ge=7, le=128),
):
    """
    Fit and generate real multi-step recursive forecast using LightGBM regressor.
    """
    series_df, mapping = _get_series_training_data(dataset_id, series_id)
    time_col = mapping.get("date", "date")
    target_col = mapping.get("target", "target")

    forecaster = LightgbmForecaster(
        n_estimators=n_estimators,
        learning_rate=learning_rate,
        num_leaves=num_leaves,
    )
    try:
        forecaster.fit(series_df, time_col=time_col, target_col=target_col, horizon=horizon)
        result = forecaster.forecast(horizon=horizon, dataset_id=dataset_id, series_id=series_id)
        _persist_forecast(result)
        return result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LightGBM forecast execution error: {str(e)}")


@router.post("/forecast/deepar", response_model=ForecastResult)
def generate_deepar_forecast(
    dataset_id: str = Query(...),
    series_id: str = Query(...),
    horizon: int = Query(28, ge=7, le=90),
    epochs: int = Query(15, ge=1, le=100),
    batch_size: int = Query(16, ge=1, le=128),
    hidden_dim: int = Query(20, ge=4, le=128),
    num_samples: int = Query(100, ge=10, le=500),
):
    """
    Fit and generate real probabilistic multi-horizon forecast using Darts DeepAR (RNN with GaussianLikelihood).
    """
    series_df, mapping = _get_series_training_data(dataset_id, series_id)
    time_col = mapping.get("date", "date")
    target_col = mapping.get("target", "target")

    forecaster = DeeparForecaster(
        epochs=epochs,
        batch_size=batch_size,
        hidden_dim=hidden_dim,
        num_samples=num_samples,
    )
    try:
        forecaster.fit(series_df, time_col=time_col, target_col=target_col, horizon=horizon)
        result = forecaster.forecast(horizon=horizon, dataset_id=dataset_id, series_id=series_id)
        _persist_forecast(result)
        return result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DeepAR forecast execution error: {str(e)}")


@router.post("/forecast/tft", response_model=ForecastResult)
def generate_tft_forecast(
    dataset_id: str = Query(...),
    series_id: str = Query(...),
    horizon: int = Query(28, ge=7, le=90),
    epochs: int = Query(15, ge=1, le=100),
    batch_size: int = Query(16, ge=1, le=128),
    hidden_size: int = Query(16, ge=4, le=128),
    attention_heads: int = Query(2, ge=1, le=8),
):
    """
    Fit and generate real multi-horizon forecast using Darts Temporal Fusion Transformer (TFT).
    """
    series_df, mapping = _get_series_training_data(dataset_id, series_id)
    time_col = mapping.get("date", "date")
    target_col = mapping.get("target", "target")

    forecaster = TftForecaster(
        epochs=epochs,
        batch_size=batch_size,
        hidden_size=hidden_size,
        num_attention_heads=attention_heads,
    )
    try:
        forecaster.fit(series_df, time_col=time_col, target_col=target_col, horizon=horizon)
        result = forecaster.forecast(horizon=horizon, dataset_id=dataset_id, series_id=series_id)
        _persist_forecast(result)
        return result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TFT forecast execution error: {str(e)}")


@router.post("/forecast/generate", response_model=ForecastResult)
def generate_unified_forecast(req: ForecastRequest):
    """
    Unified multi-horizon forecasting endpoint delegating to UnifiedForecastEngine:
    Supports arima, sarima, prophet, lightgbm, deepar, tft, and automatic mode.
    """
    from ..forecasting.engine import UnifiedForecastEngine

    try:
        return UnifiedForecastEngine.execute(req)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except RuntimeError as re:
        raise HTTPException(status_code=500, detail=str(re))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Forecast generation failed: {str(e)}")


@router.post("/evaluation/backtest", response_model=EvaluationSummaryResponse)
def run_evaluation_backtest(req: BacktestRequest):
    """
    Execute chronological rolling-origin walk-forward backtesting across models, horizons, and series.
    Calculates authentic out-of-sample MAPE and RMSE, computes model rankings, detects ties,
    and caches evaluation results.
    """
    try:
        results = BacktestingEngine.run_backtest_suite(
            dataset_id=req.dataset_id,
            series_ids=req.series_ids,
            store_id=req.store_id,
            category=req.category,
            item_id=req.item_id,
            models=req.models,
            horizons=req.horizons,
            n_folds=req.n_folds,
        )
        return results
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backtesting execution failed: {str(e)}")


@router.get("/evaluation/{dataset_id}", response_model=EvaluationSummaryResponse)
def get_dataset_evaluation(
    dataset_id: str,
    store_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    item_id: Optional[str] = Query(None),
    series_id: Optional[str] = Query(None),
    horizon: Optional[int] = Query(None),
):
    """
    Retrieve cached evaluation and backtesting summary for a dataset and scope.
    """
    cached = BacktestingEngine.get_evaluation_for_dataset(
        dataset_id,
        store_id=store_id,
        category=category,
        item_id=item_id,
        series_id=series_id,
        horizon=horizon,
    )
    if not cached:
        raise HTTPException(
            status_code=404,
            detail=f"No backtesting evaluation found for dataset '{dataset_id}'. Run /api/evaluation/backtest first."
        )
    return cached


@router.get("/evaluation/{dataset_id}/comparison")
def get_evaluation_comparison_matrices(
    dataset_id: str,
    store_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    item_id: Optional[str] = Query(None),
    series_id: Optional[str] = Query(None),
    horizon: Optional[int] = Query(None),
):
    """
    Get Model x Horizon benchmark matrices (Table 1: MAPE, Table 2: RMSE)
    and best models per horizon / overall for specific scope.
    """
    cached = BacktestingEngine.get_evaluation_for_dataset(
        dataset_id,
        store_id=store_id,
        category=category,
        item_id=item_id,
        series_id=series_id,
        horizon=horizon,
    )
    if not cached:
        raise HTTPException(
            status_code=404,
            detail=f"No backtesting evaluation found for dataset '{dataset_id}'."
        )
    # If series_id is specifically requested, extract series-specific model x horizon matrices
    if series_id:
        series_mapes = {m: {} for m in cached.get("models_evaluated", [])}
        series_rmses = {m: {} for m in cached.get("models_evaluated", [])}
        found_series_eval = False
        for item in cached.get("table_3_series_evaluations", []):
            if str(item.get("series_id")) == str(series_id):
                found_series_eval = True
                m = item.get("model")
                h = item.get("horizon")  # e.g. "7D" or "28D"
                if m in series_mapes:
                    series_mapes[m][h] = item.get("mape")
                    series_rmses[m][h] = item.get("rmse")

        if found_series_eval:
            # Calculate series-specific best_per_horizon and best_model_overall from series_mapes and series_rmses
            series_best_per_horizon = {}
            for h in cached.get("horizons_evaluated", []):
                h_str = str(h) if str(h).endswith("D") else f"{h}D"
                # Find model with minimum valid MAPE for horizon h
                valid_models = [
                    (m, series_mapes[m].get(h_str))
                    for m in series_mapes
                    if series_mapes[m].get(h_str) is not None
                ]
                if valid_models:
                    min_mape = min(vm[1] for vm in valid_models)
                    best_m = next(vm[0] for vm in valid_models if vm[1] == min_mape)
                    best_rmse = series_rmses.get(best_m, {}).get(h_str)
                    series_best_per_horizon[h_str] = {
                        "best_model": best_m,
                        "mape": min_mape,
                        "rmse": best_rmse,
                        "is_tie": False,
                        "tied_models": [],
                    }
                else:
                    series_best_per_horizon[h_str] = None

            # Calculate best model overall for this series
            model_avg_mapes = {}
            for m in series_mapes:
                vals = [v for v in series_mapes[m].values() if v is not None]
                if vals:
                    model_avg_mapes[m] = sum(vals) / len(vals)
            series_best_overall = None
            if model_avg_mapes:
                best_overall_m = min(model_avg_mapes, key=model_avg_mapes.get)
                series_best_overall = {
                    "model": best_overall_m,
                    "overall_mape": round(model_avg_mapes[best_overall_m], 2),
                    "horizons_covered": len([v for v in series_mapes[best_overall_m].values() if v is not None]),
                    "evaluated_horizons": [h for h, v in series_mapes[best_overall_m].items() if v is not None],
                }

            return {
                "dataset_id": dataset_id,
                "series_id": series_id,
                "models_evaluated": cached.get("models_evaluated", []),
                "horizons_evaluated": cached.get("horizons_evaluated", []),
                "table_1_model_x_horizon_mape": series_mapes,
                "table_2_model_x_horizon_rmse": series_rmses,
                "best_per_horizon": series_best_per_horizon,
                "best_model_overall": series_best_overall,
                "execution_duration_ms": cached.get("execution_duration_ms", 0.0),
                "is_series_specific": True,
            }

    return {
        "dataset_id": dataset_id,
        "models_evaluated": cached.get("models_evaluated", []),
        "horizons_evaluated": cached.get("horizons_evaluated", []),
        "table_1_model_x_horizon_mape": cached.get("table_1_model_x_horizon_mape", {}),
        "table_2_model_x_horizon_rmse": cached.get("table_2_model_x_horizon_rmse", {}),
        "best_per_horizon": cached.get("best_per_horizon", {}),
        "best_model_overall": cached.get("best_model_overall"),
        "execution_duration_ms": cached.get("execution_duration_ms", 0.0),
    }


@router.get("/evaluation/{dataset_id}/series/{series_id}")
def get_series_evaluation(dataset_id: str, series_id: str):
    """
    Get detailed backtesting breakdown for a specific series.
    """
    cached = BacktestingEngine.get_evaluation_for_dataset(dataset_id)
    if not cached:
        raise HTTPException(
            status_code=404,
            detail=f"No backtesting evaluation found for dataset '{dataset_id}'."
        )

    series_evals = [
        s for s in cached.get("table_3_series_evaluations", [])
        if str(s.get("series_id")) == str(series_id)
    ]
    detailed = [
        d for d in cached.get("series_details", [])
        if str(d.get("series_id")) == str(series_id)
    ]

    return {
        "dataset_id": dataset_id,
        "series_id": series_id,
        "summary": series_evals,
        "details": detailed,
    }


@router.get("/evaluation/{dataset_id}/best-model")
def get_dataset_best_model(
    dataset_id: str,
    series_id: Optional[str] = None,
    horizon: Optional[int] = None,
):
    """
    Resolve empirically verified best model from backtesting.
    """
    cached = BacktestingEngine.get_evaluation_for_dataset(dataset_id)
    if not cached:
        raise HTTPException(
            status_code=404,
            detail=f"No backtesting evaluation found for dataset '{dataset_id}'."
        )

    if series_id and horizon:
        best_model = BacktestingEngine.get_best_model_for_series_horizon(
            dataset_id=dataset_id,
            series_id=series_id,
            horizon=horizon,
        )
        return {
            "dataset_id": dataset_id,
            "series_id": series_id,
            "horizon": f"{horizon}D",
            "best_model": best_model,
        }

    return {
        "dataset_id": dataset_id,
        "best_per_horizon": cached.get("best_per_horizon", {}),
        "best_model_overall": cached.get("best_model_overall"),
    }


def _resolve_insights_for_series(
    dataset_id: str,
    series_id: Optional[str] = None,
    store_id: Optional[str] = None,
    category: Optional[str] = None,
    item_id: Optional[str] = None,
    model: str = "automatic",
    horizon: int = 28,
) -> BusinessInsightsResponse:
    from ..forecasting.engine import UnifiedForecastEngine

    # Retrieve verified single-series data through UnifiedForecastEngine to ensure
    # exact scope resolution and cleaned data usage
    try:
        series_df, mapping, resolved_series = UnifiedForecastEngine.get_series_data(
            dataset_id=dataset_id,
            series_id=series_id,
            store_id=store_id,
            category=category,
            item_id=item_id,
        )
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))

    # Generate forecast for the series
    forecast_req = ForecastRequest(
        dataset_id=dataset_id,
        series_id=str(resolved_series),
        store_id=store_id,
        category=category,
        item_id=item_id,
        horizon=horizon,
        model=model,
    )
    forecast_res = UnifiedForecastEngine.execute(forecast_req)

    # Optional evaluation summary
    eval_summary = BacktestingEngine.get_evaluation_for_dataset(
        dataset_id,
        store_id=store_id,
        category=category,
        item_id=item_id,
        series_id=resolved_series,
        horizon=horizon,
    )

    insights = BusinessInsightEngine.generate_insights(
        forecast_result=forecast_res,
        historical_df=series_df,
        mapping=mapping,
        evaluation_summary=eval_summary,
        store_id=store_id,
        category=category,
        item_id=item_id,
        model_key=model,  # canonical key e.g. "arima"
    )
    return insights


@router.post("/insights/generate", response_model=BusinessInsightsResponse)
def generate_insights_endpoint(req: InsightRequest):
    """
    Generate evidence-based actionable business insights from actual forecast and historical data.
    """
    try:
        return _resolve_insights_for_series(
            dataset_id=req.dataset_id,
            series_id=req.series_id,
            store_id=req.store_id,
            category=req.category,
            item_id=req.item_id,
            model=req.model,
            horizon=req.horizon,
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Insight generation failed: {str(e)}")


@router.get("/insights/{dataset_id}", response_model=BusinessInsightsResponse)
def get_dataset_insights(
    dataset_id: str,
    series_id: Optional[str] = None,
    store_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    item_id: Optional[str] = Query(None),
    model: str = Query("automatic"),
    horizon: int = Query(28, ge=7, le=90),
):
    """
    Retrieve cached or generated business insights for a dataset and scope.
    """
    cached = BusinessInsightEngine.get_cached_insights(
        dataset_id=dataset_id,
        series_id=series_id,
        horizon=horizon,
        model=model,
        store_id=store_id,
        category=category,
        item_id=item_id,
    )
    if cached:
        return cached

    entry = CLEANED_DATASET_STORE.get(dataset_id) or get_dataset(dataset_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Dataset with ID '{dataset_id}' not found.")

    try:
        return _resolve_insights_for_series(
            dataset_id=dataset_id,
            series_id=series_id,
            store_id=store_id,
            category=category,
            item_id=item_id,
            model=model,
            horizon=horizon,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Insight retrieval failed: {str(e)}")


@router.get("/insights/{dataset_id}/series/{series_id}", response_model=BusinessInsightsResponse)
def get_series_insights(
    dataset_id: str,
    series_id: str,
    store_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    item_id: Optional[str] = Query(None),
    model: str = Query("automatic"),
    horizon: int = Query(28, ge=7, le=90),
):
    """
    Retrieve or generate business insights for a specific series and scope.
    """
    try:
        cached = BusinessInsightEngine.get_cached_insights(
            dataset_id=dataset_id,
            series_id=series_id,
            horizon=horizon,
            model=model,
            store_id=store_id,
            category=category,
            item_id=item_id,
        )
        if cached:
            return cached

        return _resolve_insights_for_series(
            dataset_id=dataset_id,
            series_id=series_id,
            store_id=store_id,
            category=category,
            item_id=item_id,
            model=model,
            horizon=horizon,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Series insight retrieval failed: {str(e)}")


@router.get("/monitoring/{dataset_id}", response_model=MonitoringReport)
def get_dataset_monitoring(
    dataset_id: str,
    series_id: Optional[str] = Query(None),
    store_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    item_id: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    horizon: Optional[int] = Query(None),
):
    """
    Evaluate ongoing model performance across evaluation folds and detect potential accuracy drift
    scoped to the active series, store, category, item, model, and horizon.
    """
    entry = CLEANED_DATASET_STORE.get(dataset_id) or get_dataset(dataset_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Dataset with ID '{dataset_id}' not found.")

    try:
        report = MonitoringTracker.evaluate_monitoring_status(
            dataset_id=dataset_id,
            series_id=series_id,
            store_id=store_id,
            category=category,
            item_id=item_id,
            model=model,
            horizon=horizon,
        )
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Monitoring evaluation failed: {str(e)}")




