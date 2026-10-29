"""
Unified Multi-Horizon Forecasting Engine & Model Registry (Phase 7)
ForecastIQ Backend

Responsibilities:
1. Model Registry / Factory:
   - Resolves model by string identifier ("arima", "sarima", "prophet", "lightgbm", "deepar", "tft", "automatic").
2. Unified Execution Pipeline:
   - Retrieves dataset from cleaned/raw store and verifies forecast readiness.
   - Extracts single-series slice and isolates observations strictly by series_id.
   - Verifies horizon validity and history sufficiency via HorizonManager.
   - Instantiates forecaster from registry with validated hyperparameters.
   - Executes fit and forecast, returning standardized ForecastResult.
   - Supports 'automatic' mode: runs all implemented models on the selected series/horizon and returns comparable results.
3. Strict Compliance:
   - No fake intervals.
   - No M5-specific assumptions hardcoded into the engine.
"""
import time
import logging
from typing import Dict, Any, Type, Optional, List, Tuple
import pandas as pd

from ..data.schema import (
    ForecastResult,
    ForecastRequest,
    ForecastPoint,
    PipelineStatus,
)
from ..data.loader import get_dataset, detect_candidate_columns
from ..data.cleaner import CLEANED_DATASET_STORE
from ..models.base import BaseForecaster
from ..models.arima import ArimaForecaster
from ..models.sarima import SarimaForecaster
from ..models.prophet_model import ProphetForecaster
from ..models.lightgbm import LightgbmForecaster
from ..models.deepar import DeeparForecaster
from ..models.tft import TftForecaster
from ..models.config import ModelDefaults
from .horizon import HorizonManager
from ..scope import (
    apply_scope_filters,
    build_scope_dict,
    extract_scope_values_from_frame,
    resolve_series_id,
    user_friendly_insufficient_history,
)

logger = logging.getLogger("forecastiq.forecasting.engine")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)


class ModelRegistry:
    """
    Central registry and factory for all forecasting models.
    Supports arima, sarima, prophet, lightgbm, deepar, tft.
    """
    _registry: Dict[str, Type[BaseForecaster]] = {
        "arima": ArimaForecaster,
        "sarima": SarimaForecaster,
        "prophet": ProphetForecaster,
        "lightgbm": LightgbmForecaster,
        "lgbm": LightgbmForecaster,
        "deepar": DeeparForecaster,
        "tft": TftForecaster,
        "temporal_fusion_transformer": TftForecaster,
    }

    @classmethod
    def list_models(cls) -> List[str]:
        """List distinct canonical model identifiers."""
        return ["arima", "sarima", "prophet", "lightgbm", "deepar", "tft"]

    @classmethod
    def is_registered(cls, model_name: str) -> bool:
        """Check if model name is registered."""
        return model_name.lower().strip() in cls._registry or model_name.lower().strip() == "automatic"

    @classmethod
    def create(cls, model_name: str, **kwargs) -> BaseForecaster:
        """
        Factory method to instantiate a forecaster by name with optional hyperparameters.
        """
        key = model_name.lower().strip()
        if key not in cls._registry:
            supported = ", ".join(cls.list_models() + ["automatic"])
            raise ValueError(f"Model is unavailable: '{model_name}'. Supported models are: {supported}.")

        forecaster_cls = cls._registry[key]
        return forecaster_cls(**kwargs)


class UnifiedForecastEngine:
    """
    Unified Multi-Horizon Forecasting Engine.
    Provides standard entrypoint for single-series multi-horizon forecasting across all architectures.
    """

    @classmethod
    def get_series_data(
        cls,
        dataset_id: str,
        series_id: Optional[str] = None,
        store_id: Optional[str] = None,
        category: Optional[str] = None,
        item_id: Optional[str] = None,
    ) -> Tuple[pd.DataFrame, Dict[str, Any], str]:
        """
        Retrieve and isolate a single series using the full ActiveScope.
        Store/category/item filters are applied before series isolation.
        """
        entry = CLEANED_DATASET_STORE.get(dataset_id) or get_dataset(dataset_id)
        if not entry:
            raise ValueError(f"Dataset with ID '{dataset_id}' not found.")

        df = entry["df"]
        mapping = entry.get("mapping") or detect_candidate_columns(list(df.columns))

        series_col = mapping.get("series_id") or "series_id"
        date_col = mapping.get("date") or "date"
        target_col = mapping.get("target") or "target"
        composite_keys = mapping.get("composite_series_keys") or []

        if composite_keys and all(ck in df.columns for ck in composite_keys) and series_col not in df.columns:
            df["series_id"] = df[composite_keys].astype(str).agg("__".join, axis=1)
            series_col = "series_id"
        elif series_col not in df.columns:
            cand_entities = mapping.get("candidate_entity_columns") or []
            cand_in_df = [c for c in cand_entities if c in df.columns]
            if len(cand_in_df) > 1:
                df["series_id"] = df[cand_in_df].astype(str).agg("__".join, axis=1)
                series_col = "series_id"
            elif len(cand_in_df) == 1:
                series_col = cand_in_df[0]
            elif "series_id" in df.columns:
                series_col = "series_id"
            else:
                df["series_id"] = "default_series"
                series_col = "series_id"

        # Defensive fallback resolution
        if date_col not in df.columns:
            for cand in ["date", "datetime", "timestamp", "ds", "time", "d", "month", "observation_date", "order_date"]:
                m = next((c for c in df.columns if c.lower() == cand), None)
                if m:
                    date_col = m
                    break
        if target_col not in df.columns:
            for cand in ["weekly_sales", "monthly_sales", "daily_sales", "total_sales", "sales", "target", "demand", "units", "quantity", "val", "value", "revenue", "y", "pjme_mw", "#passengers"]:
                m = next((c for c in df.columns if c.lower() == cand), None)
                if m:
                    target_col = m
                    break

        if date_col not in df.columns:
            raise ValueError(f"Date column '{date_col}' not found in dataset. Available columns: {list(df.columns)}")
        if target_col not in df.columns:
            raise ValueError(f"Target column '{target_col}' not found in dataset. Available columns: {list(df.columns)}")

        resolved_series = resolve_series_id(
            df,
            mapping=mapping,
            series_id=series_id,
            store_id=store_id,
            category=category,
            item_id=item_id,
        )
        scoped_df, _ = apply_scope_filters(
            df,
            mapping=mapping,
            store_id=store_id,
            category=category,
            item_id=item_id,
            series_id=resolved_series,
        )
        series_df = scoped_df.copy()
        if series_df.empty:
            available_series = list(df[series_col].astype(str).unique()[:5])
            raise ValueError(f"Series '{resolved_series}' not found. Available sample: {available_series}")

        if series_df[target_col].isna().any():
            raise ValueError("Series contains unresolved missing target values.")

        return series_df, mapping, resolved_series

    @classmethod
    def build_forecaster_for_request(cls, req: ForecastRequest) -> BaseForecaster:
        """Instantiate forecaster with request-specific configuration."""
        model_name = req.model.lower().strip()

        if model_name in ["arima"]:
            cfg = req.arima_config
            return ModelRegistry.create(
                "arima",
                p=cfg.p if cfg else ModelDefaults.ARIMA_P,
                d=cfg.d if cfg else ModelDefaults.ARIMA_D,
                q=cfg.q if cfg else ModelDefaults.ARIMA_Q,
            )
        elif model_name in ["sarima"]:
            cfg = req.sarima_config
            return ModelRegistry.create(
                "sarima",
                order=(cfg.p if cfg else 1, cfg.d if cfg else 1, cfg.q if cfg else 1),
                seasonal_order=(cfg.P if cfg else 1, cfg.D if cfg else 0, cfg.Q if cfg else 1, cfg.seasonal_period if cfg else 7),
            )
        elif model_name in ["prophet"]:
            cfg = req.prophet_config
            return ModelRegistry.create(
                "prophet",
                weekly_seasonality=cfg.weekly_seasonality if cfg else ModelDefaults.PROPHET_WEEKLY_SEASONALITY,
                yearly_seasonality=cfg.yearly_seasonality if cfg else ModelDefaults.PROPHET_YEARLY_SEASONALITY,
            )
        elif model_name in ["lightgbm", "lgbm"]:
            cfg = req.lightgbm_config
            return ModelRegistry.create(
                "lightgbm",
                n_estimators=cfg.n_estimators if cfg else ModelDefaults.LGBM_N_ESTIMATORS,
                learning_rate=cfg.learning_rate if cfg else ModelDefaults.LGBM_LEARNING_RATE,
                num_leaves=cfg.num_leaves if cfg else ModelDefaults.LGBM_NUM_LEAVES,
                max_depth=cfg.max_depth if cfg else ModelDefaults.LGBM_MAX_DEPTH,
                subsample=cfg.subsample if cfg else ModelDefaults.LGBM_SUBSAMPLE,
                random_state=cfg.random_state if cfg else ModelDefaults.LGBM_RANDOM_STATE,
            )
        elif model_name in ["deepar"]:
            cfg = req.deepar_config
            return ModelRegistry.create(
                "deepar",
                epochs=cfg.epochs if cfg else ModelDefaults.DEEPAR_EPOCHS,
                batch_size=cfg.batch_size if cfg else ModelDefaults.DEEPAR_BATCH_SIZE,
                hidden_dim=cfg.hidden_dim if cfg else ModelDefaults.DEEPAR_HIDDEN_DIM,
                num_samples=cfg.num_samples if cfg else ModelDefaults.DEEPAR_NUM_SAMPLES,
                dropout=cfg.dropout if cfg else ModelDefaults.DEEPAR_DROPOUT,
                random_state=cfg.random_state if cfg else ModelDefaults.DEEPAR_RANDOM_STATE,
            )
        elif model_name in ["tft", "temporal_fusion_transformer"]:
            cfg = req.tft_config
            return ModelRegistry.create(
                "tft",
                epochs=cfg.epochs if cfg else ModelDefaults.TFT_EPOCHS,
                batch_size=cfg.batch_size if cfg else ModelDefaults.TFT_BATCH_SIZE,
                hidden_size=cfg.hidden_size if cfg else ModelDefaults.TFT_HIDDEN_SIZE,
                num_attention_heads=cfg.num_attention_heads if cfg else ModelDefaults.TFT_ATTENTION_HEADS,
                dropout=cfg.dropout if cfg else ModelDefaults.TFT_DROPOUT,
                random_state=cfg.random_state if cfg else ModelDefaults.TFT_RANDOM_STATE,
            )
        else:
            supported = ", ".join(ModelRegistry.list_models() + ["automatic"])
            raise ValueError(f"Model is unavailable: '{model_name}'. Supported models are: {supported}.")

    @classmethod
    def generate_single_forecast(
        cls,
        forecaster: BaseForecaster,
        series_df: pd.DataFrame,
        mapping: Dict[str, Any],
        horizon: int,
        dataset_id: str,
        series_id: str,
    ) -> ForecastResult:
        """
        Fit forecaster on series data and execute out-of-sample forecast.
        """
        time_col = mapping.get("date") or "date"
        target_col = mapping.get("target") or "target"
        if time_col not in series_df.columns:
            for cand in ["date", "datetime", "timestamp", "ds", "time", "d", "month", "observation_date", "order_date"]:
                m = next((c for c in series_df.columns if c.lower() == cand), None)
                if m:
                    time_col = m
                    break
        if target_col not in series_df.columns:
            for cand in ["weekly_sales", "monthly_sales", "daily_sales", "total_sales", "sales", "target", "demand", "units", "quantity", "val", "value", "revenue", "y", "pjme_mw", "#passengers"]:
                m = next((c for c in series_df.columns if c.lower() == cand), None)
                if m:
                    target_col = m
                    break

        HorizonManager.validate_history_sufficiency(
            horizon=horizon,
            observation_count=len(series_df),
            model_name=forecaster.model_name
        )

        forecaster.fit(
            series_df,
            time_col=time_col,
            target_col=target_col,
            horizon=horizon
        )

        result = forecaster.forecast(
            horizon=horizon,
            dataset_id=dataset_id,
            series_id=series_id
        )

        # Output validation
        if len(result.forecast) != horizon:
            raise RuntimeError(
                f"Forecast generation failed: Expected {horizon} points, but received {len(result.forecast)}."
            )

        requested = (forecaster.model_name or "").lower()
        returned = (result.model or "").lower()
        if requested and requested not in returned and returned not in requested:
            result.model = forecaster.model_name

        return result

    @classmethod
    def execute(cls, req: ForecastRequest) -> ForecastResult:
        """
        Main engine dispatch method:
        - Validates model availability
        - Validates horizon
        - Retrieves series data
        - Handles 'automatic' mode or routes to the single selected architecture
        - Logs execution metadata
        """
        start_time = time.time()
        model_key = req.model.lower().strip()
        if model_key == "auto":
            model_key = "automatic"
            req.model = "automatic"
        if not ModelRegistry.is_registered(model_key):
            supported = ", ".join(ModelRegistry.list_models() + ["automatic"])
            raise ValueError(f"Model is unavailable: '{req.model}'. Supported models are: {supported}.")

        horizon = HorizonManager.validate_horizon(req.horizon)
        try:
            series_df, mapping, resolved_series = cls.get_series_data(
                req.dataset_id,
                series_id=req.series_id,
                store_id=req.store_id,
                category=req.category,
                item_id=req.item_id,
            )
        except ValueError as ve:
            friendly = user_friendly_insufficient_history(ve)
            if friendly:
                raise ValueError(friendly["message"] + f" Available: {friendly['available']} observations. Required: {friendly['required']} observations.") from ve
            raise
        req.series_id = resolved_series

        # Handle 'automatic' mode (orchestrate multi-model generation)
        if model_key == "automatic":
            result = cls._execute_automatic_mode(req, series_df, mapping, horizon, start_time)
        else:
            forecaster = cls.build_forecaster_for_request(req)
            try:
                result = cls.generate_single_forecast(
                    forecaster=forecaster,
                    series_df=series_df,
                    mapping=mapping,
                    horizon=horizon,
                    dataset_id=req.dataset_id,
                    series_id=req.series_id,
                )
            except ValueError as ve:
                friendly = user_friendly_insufficient_history(ve)
                if friendly:
                    raise ValueError(
                        f"{friendly['message']} Available: {friendly['available']} observations. "
                        f"Required: {friendly['required']} observations."
                    ) from ve
                raise

        dim = extract_scope_values_from_frame(
            series_df, mapping, req.store_id, req.category, req.item_id
        )
        result.store_id = dim["store_id"]
        result.category = dim["category"]
        result.item_id = dim["item_id"]
        result.series_id = req.series_id
        result.forecast_horizon = horizon
        result.scope = build_scope_dict(
            dataset_id=req.dataset_id,
            store_id=result.store_id,
            category=result.category,
            item_id=result.item_id,
            series_id=result.series_id,
            model=model_key if model_key != "automatic" else result.model,
            horizon=horizon,
        )

        logger.info(
            f"Forecast completed: dataset={req.dataset_id}, series={req.series_id}, "
            f"model={result.model}, horizon={horizon}D, status={result.status}, "
            f"exec_time={result.execution_time_ms}ms"
        )

        try:
            from ..db.mongo import MongoRepository
            saved = MongoRepository.save_forecast_result(result.model_dump())
            if not saved:
                logger.warning(f"MongoRepository.save_forecast_result returned False for dataset={req.dataset_id}, series={req.series_id}")
        except Exception as ex:
            logger.warning(f"Failed to persist forecast result to MongoDB for dataset={req.dataset_id}: {ex}")

        return result

    @classmethod
    def _execute_automatic_mode(
        cls,
        req: ForecastRequest,
        series_df: pd.DataFrame,
        mapping: Dict[str, Any],
        horizon: int,
        start_time: float
    ) -> ForecastResult:
        """
        Automatic model mode:
        Orchestrates forecasts across all implemented models for comparison.
        Returns the primary standardized result with multi-model results packaged in components.
        NOTE: Does NOT declare 'best model' yet (evaluation / backtesting phase will determine metrics).
        """
        from ..evaluation.backtesting import BacktestingEngine
        best_model_name = BacktestingEngine.get_best_model_for_series_horizon(
            dataset_id=req.dataset_id,
            series_id=req.series_id,
            horizon=horizon,
            store_id=req.store_id,
            category=req.category,
            item_id=req.item_id,
        )

        # Automatic uses the empirically best model for THIS scope, and falls back to the
        # full six-model comparison when no scope-specific evaluation exists yet.
        if best_model_name:
            candidate_models = [best_model_name.lower()]
        else:
            candidate_models = ["arima", "sarima", "prophet", "lightgbm", "deepar", "tft"]

        model_results: Dict[str, Any] = {}
        successful_results: List[ForecastResult] = []

        for m_name in candidate_models:
            try:
                sub_req = req.model_copy(update={"model": m_name})
                forecaster = cls.build_forecaster_for_request(sub_req)
                res = cls.generate_single_forecast(
                    forecaster=forecaster,
                    series_df=series_df,
                    mapping=mapping,
                    horizon=horizon,
                    dataset_id=req.dataset_id,
                    series_id=req.series_id,
                )
                model_results[m_name] = {
                    "model": res.model,
                    "forecast": res.forecast,
                    "lower_bound": res.lower_bound,
                    "upper_bound": res.upper_bound,
                    "execution_time_ms": res.execution_time_ms,
                    "status": "SUCCESS"
                }
                successful_results.append(res)
            except Exception as e:
                model_results[m_name] = {
                    "model": m_name.upper(),
                    "status": "FAILED",
                    "error": str(e)
                }

        if not successful_results:
            raise RuntimeError(f"Forecast generation failed for all models in automatic mode: {model_results}")

        # If a best model was evaluated, use its result as primary; otherwise first successful
        base_result = successful_results[0]
        if best_model_name:
            for r in successful_results:
                if best_model_name.lower() in r.model.lower():
                    base_result = r
                    break

        exec_total = round((time.time() - start_time) * 1000, 2)

        selection_note = (
            f"Selected '{base_result.model}' based on lowest empirical backtested error."
            if best_model_name else
            "Automatic mode generated forecasts across all models. Best-model selection is determined after running backtesting evaluation."
        )

        auto_model_label = f"Automatic ({base_result.model})"
        return ForecastResult(
            dataset_id=req.dataset_id,
            series_id=req.series_id,
            model=auto_model_label,
            forecast_horizon=horizon,
            dates=base_result.dates,
            forecast=base_result.forecast,
            lower_bound=base_result.lower_bound,
            upper_bound=base_result.upper_bound,
            points=base_result.points,
            components={
                "orchestrator_mode": "automatic",
                "empirically_evaluated_winner": best_model_name or "Not yet backtested",
                "primary_model_used": base_result.model,
                "selected_model": base_result.model,
                "models_executed": len(model_results),
                "successful_models": len(successful_results),
                "model_forecasts": model_results,
                "selection_note": selection_note,
            },
            training_start=base_result.training_start,
            training_end=base_result.training_end,
            forecast_start=base_result.forecast_start,
            forecast_end=base_result.forecast_end,
            execution_time_ms=exec_total,
            status="SUCCESS",
            notes=[
                f"Automatic mode executed {len(successful_results)} model(s) at {horizon}-day horizon for the current scope.",
                f"Primary output: {base_result.model}.",
                selection_note,
            ]
        )
