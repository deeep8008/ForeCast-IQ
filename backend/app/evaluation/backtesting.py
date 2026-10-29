"""
Backtesting and Evaluation Engine (Phase 8)
ForecastIQ Backend

Implements:
1. Rolling-Origin / Walk-Forward Temporal Backtesting:
   - Evaluates models over chronological folds without future data leakage.
   - For each fold:
       Train on observations up to origin t
       Forecast horizon h steps ahead (t+1 ... t+h)
       Compare against held-out actuals for (t+1 ... t+h)
       Advance origin forward by step_size
2. Multi-Horizon Evaluations (7D, 28D, 90D).
3. Fair Model Comparison & Ranking:
   - Compares all models on identical temporal slices.
   - Computes horizon degradation and cross-horizon consistency.
   - Supports series-level and dataset-level aggregation.
4. Automatic Best-Model Selection:
   - Chooses best model based strictly on empirical backtest metrics (lowest error).
   - Reports ties/near-ties where models are within 0.2% MAPE.
"""
import time
import logging
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np

from .metrics import EvaluationMetrics
from ..forecasting.engine import ModelRegistry, UnifiedForecastEngine
from ..forecasting.horizon import HorizonManager
from ..data.schema import ForecastRequest
from ..data.loader import get_dataset, detect_candidate_columns
from ..data.cleaner import CLEANED_DATASET_STORE, split_series_chronological_80_20

logger = logging.getLogger("forecastiq.evaluation.backtesting")

# In-memory evaluation cache: dataset_id -> evaluation results
EVALUATION_CACHE: Dict[str, Dict[str, Any]] = {}


class BacktestingEngine:
    """
    Chronological rolling-origin backtesting engine.
    """

    @classmethod
    def generate_rolling_origin_folds(
        cls,
        series_df: pd.DataFrame,
        time_col: str,
        horizon: int,
        n_folds: int = 3,
        step_size: Optional[int] = None,
        min_train_size: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Create chronological rolling-origin folds.
        Guarantees that train and test never overlap and future data is never leaked into training.
        """
        sorted_df = series_df.sort_values(by=time_col).reset_index(drop=True)
        total_obs = len(sorted_df)

        meta = HorizonManager.get_metadata(horizon)
        default_min_train = meta.get("min_history_required", horizon * 2)
        min_train = min_train_size or default_min_train
        step = step_size or horizon

        # Check total feasibility: min_train + n_folds * horizon
        # If series is tight, adjust n_folds dynamically
        max_possible_folds = max(1, (total_obs - min_train) // step)
        actual_folds_count = min(n_folds, max_possible_folds)

        if total_obs < min_train + horizon:
            raise ValueError(
                f"Insufficient history for {horizon}-day backtesting. "
                f"Series has {total_obs} observations, requires at least {min_train + horizon}."
            )

        folds: List[Dict[str, Any]] = []

        # Construct origins from newest back to oldest
        # For fold k in reverse: test ends at total_obs - (k * step), test starts at end - horizon
        for k in range(actual_folds_count):
            # Calculate test cutoff
            test_end_idx = total_obs - (actual_folds_count - 1 - k) * step
            test_start_idx = test_end_idx - horizon
            train_end_idx = test_start_idx

            if train_end_idx < min_train:
                continue

            train_slice = sorted_df.iloc[:train_end_idx].copy()
            test_slice = sorted_df.iloc[test_start_idx:test_end_idx].copy()

            folds.append({
                "fold_number": len(folds) + 1,
                "train_df": train_slice,
                "test_df": test_slice,
                "train_start": str(train_slice[time_col].iloc[0])[:10],
                "train_end": str(train_slice[time_col].iloc[-1])[:10],
                "forecast_start": str(test_slice[time_col].iloc[0])[:10],
                "forecast_end": str(test_slice[time_col].iloc[-1])[:10],
                "train_count": len(train_slice),
                "test_count": len(test_slice),
            })

        if not folds:
            raise ValueError(
                f"Could not construct valid backtest folds for horizon {horizon}D with {total_obs} observations."
            )

        return folds

    @classmethod
    def evaluate_model_on_series(
        cls,
        dataset_id: str,
        series_id: str,
        model_name: str,
        horizon: int,
        series_df: pd.DataFrame,
        mapping: Dict[str, Any],
        n_folds: int = 2,
        model_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate a single model on a single series using chronological rolling-origin backtesting.
        """
        time_col = mapping.get("date", "date")
        target_col = mapping.get("target", "target")
        model_kwargs = model_kwargs or {}

        try:
            folds = cls.generate_rolling_origin_folds(
                series_df=series_df,
                time_col=time_col,
                horizon=horizon,
                n_folds=n_folds,
            )
        except ValueError as ve:
            return {
                "dataset_id": dataset_id,
                "series_id": series_id,
                "model": model_name,
                "horizon": horizon,
                "status": "INSUFFICIENT_HISTORY",
                "error": str(ve),
                "folds": [],
                "fold_count": 0,
                "successful_folds_count": 0,
                "mape": None,
                "rmse": None,
                "mape_valid_count": 0,
                "mape_zero_actual_count": 0,
                "sample_count": 0,
                "execution_time_ms": 0.0,
            }

        fold_evaluations: List[Dict[str, Any]] = []
        all_actuals: List[float] = []
        all_predictions: List[float] = []
        total_exec_time = 0.0

        for fold_info in folds:
            fold_num = fold_info["fold_number"]
            train_df = fold_info["train_df"]
            test_df = fold_info["test_df"]
            actual_values = [float(v) for v in test_df[target_col].values]

            t0 = time.time()
            try:
                # Instantiate clean model per fold
                forecaster = ModelRegistry.create(model_name, **model_kwargs)
                forecaster.fit(train_df, time_col=time_col, target_col=target_col, horizon=horizon)
                forecast_res = forecaster.forecast(horizon=horizon, dataset_id=dataset_id, series_id=series_id)
                pred_values = forecast_res.forecast
                fold_time = round((time.time() - t0) * 1000, 2)
                total_exec_time += fold_time

                # Fold metrics
                fold_metrics = EvaluationMetrics.evaluate_forecast(actual_values, pred_values)

                fold_evaluations.append({
                    "fold": fold_num,
                    "train_start": fold_info["train_start"],
                    "train_end": fold_info["train_end"],
                    "forecast_start": fold_info["forecast_start"],
                    "forecast_end": fold_info["forecast_end"],
                    "train_count": fold_info.get("train_count"),
                    "test_count": fold_info.get("test_count"),
                    "actuals": actual_values,
                    "predictions": pred_values,
                    "mape": fold_metrics["mape"],
                    "rmse": fold_metrics["rmse"],
                    "mape_valid_count": fold_metrics["mape_valid_count"],
                    "sample_count": fold_metrics["sample_count"],
                    "execution_time_ms": fold_time,
                    "status": "SUCCESS"
                })

                all_actuals.extend(actual_values)
                all_predictions.extend(pred_values)

            except Exception as e:
                fold_evaluations.append({
                    "fold": fold_num,
                    "train_start": fold_info["train_start"],
                    "train_end": fold_info["train_end"],
                    "forecast_start": fold_info["forecast_start"],
                    "forecast_end": fold_info["forecast_end"],
                    "status": "FAILED",
                    "error": str(e),
                    "execution_time_ms": round((time.time() - t0) * 1000, 2)
                })

        # Aggregated series-level metrics across folds
        successful_folds = [f for f in fold_evaluations if f["status"] == "SUCCESS"]
        if not successful_folds:
            return {
                "dataset_id": dataset_id,
                "series_id": series_id,
                "model": model_name,
                "horizon": horizon,
                "status": "FAILED",
                "error": "All backtesting folds failed for this model.",
                "folds": fold_evaluations
            }

        overall_metrics = EvaluationMetrics.evaluate_forecast(all_actuals, all_predictions)

        # 80:20 Chronological Split Evaluation metrics
        holdout_eval: Optional[Dict[str, Any]] = None
        try:
            tr_df, te_df = split_series_chronological_80_20(series_df, time_col=time_col, train_ratio=0.8)
            if len(tr_df) >= horizon and len(te_df) >= horizon:
                forecaster_holdout = ModelRegistry.create(model_name, **model_kwargs)
                forecaster_holdout.fit(tr_df, time_col=time_col, target_col=target_col, horizon=horizon)
                h_res = forecaster_holdout.forecast(horizon=horizon, dataset_id=dataset_id, series_id=series_id)
                actual_holdout = [float(v) for v in te_df[target_col].iloc[:horizon].values]
                pred_holdout = h_res.forecast[:horizon]
                h_metrics = EvaluationMetrics.evaluate_forecast(actual_holdout, pred_holdout)
                holdout_eval = {
                    "split_policy": "80:20_chronological",
                    "train_obs": len(tr_df),
                    "test_obs": len(te_df),
                    "horizon": horizon,
                    "train_end": str(tr_df[time_col].iloc[-1])[:10],
                    "test_start": str(te_df[time_col].iloc[0])[:10],
                    "mape": h_metrics["mape"],
                    "rmse": h_metrics["rmse"],
                }
        except Exception:
            holdout_eval = None

        res_dict = {
            "dataset_id": dataset_id,
            "series_id": series_id,
            "model": model_name,
            "horizon": horizon,
            "status": "SUCCESS",
            "fold_count": len(folds),
            "successful_folds_count": len(successful_folds),
            "mape": overall_metrics["mape"],
            "rmse": overall_metrics["rmse"],
            "mape_valid_count": overall_metrics["mape_valid_count"],
            "mape_zero_actual_count": overall_metrics["mape_zero_actual_count"],
            "sample_count": overall_metrics["sample_count"],
            "execution_time_ms": round(total_exec_time, 2),
            "folds": fold_evaluations,
            "split_policy": "80:20_chronological",
        }
        if holdout_eval:
            res_dict["holdout_80_20_eval"] = holdout_eval
        return res_dict

    @classmethod
    def run_backtest_suite(
        cls,
        dataset_id: str,
        series_ids: Optional[List[str]] = None,
        store_id: Optional[str] = None,
        category: Optional[str] = None,
        item_id: Optional[str] = None,
        models: Optional[List[str]] = None,
        horizons: Optional[List[int]] = None,
        n_folds: int = 2,
    ) -> Dict[str, Any]:
        """
        Execute comprehensive multi-model, multi-horizon, multi-series backtesting.
        Stores results in EVALUATION_CACHE.
        """
        entry = CLEANED_DATASET_STORE.get(dataset_id) or get_dataset(dataset_id)
        if not entry:
            raise ValueError(f"Dataset with ID '{dataset_id}' not found.")

        df = entry["df"].copy()
        mapping = entry.get("mapping") or detect_candidate_columns(list(df.columns))
        series_col = mapping.get("series_id") or "series_id"
        composite_keys = mapping.get("composite_series_keys") or []

        if composite_keys and all(ck in df.columns for ck in composite_keys) and series_col not in df.columns:
            df["series_id"] = df[composite_keys].astype(str).agg("__".join, axis=1)
            series_col = "series_id"
        elif series_col not in df.columns:
            # Check if any candidate entity column in df matches requested series_ids
            matched_col = None
            if series_ids:
                for col in mapping.get("candidate_entity_columns") or []:
                    if col in df.columns and any(str(s) in df[col].astype(str).values for s in series_ids):
                        matched_col = col
                        break
            if matched_col:
                df["series_id"] = df[matched_col].astype(str)
                series_col = "series_id"
            else:
                df["series_id"] = "default_series"
                series_col = "series_id"

        # Resolve optional scope columns
        store_col = mapping.get("optional", {}).get("store_id") if isinstance(mapping.get("optional"), dict) else None
        if not store_col:
            for cand in ["store_id", "store", "branch"]:
                if cand in df.columns:
                    store_col = cand
                    break

        cat_col = mapping.get("optional", {}).get("category") if isinstance(mapping.get("optional"), dict) else None
        if not cat_col:
            for cand in ["category", "dept_id", "cat_id", "department"]:
                if cand in df.columns:
                    cat_col = cand
                    break

        item_col = mapping.get("optional", {}).get("item_id") if isinstance(mapping.get("optional"), dict) else None
        if not item_col:
            for cand in ["item_id", "item", "product_id", "product", "sku_id"]:
                if cand in df.columns:
                    item_col = cand
                    break

        scoped_df = df.copy()
        if store_col and store_id:
            scoped_df = scoped_df[scoped_df[store_col].astype(str) == str(store_id)]
        if cat_col and category:
            scoped_df = scoped_df[scoped_df[cat_col].astype(str) == str(category)]
        if item_col and item_id:
            scoped_df = scoped_df[scoped_df[item_col].astype(str) == str(item_id)]

        available_series = [str(s) for s in scoped_df[series_col].unique()] if len(scoped_df) > 0 else [str(s) for s in df[series_col].unique()]
        if series_ids:
            target_series = [s for s in series_ids if s in available_series] or series_ids
        else:
            target_series = available_series[:3]  # Default to first 3 series for computational speed
        # Default to all six architectures. Callers should pass an explicit
        # subset for cheap development runs; the engine never trains every series.
        target_models = models or ["arima", "sarima", "prophet", "lightgbm", "deepar", "tft"]
        target_horizons = horizons or [7, 28, 90]

        start_time = time.time()
        series_evaluations: List[Dict[str, Any]] = []

        for s_id in target_series:
            series_slice = df[df[series_col].astype(str) == str(s_id)].copy()
            if series_slice.empty:
                continue

            for h in target_horizons:
                for m in target_models:
                    # Conservative configuration for fast test execution
                    m_kwargs = {}
                    if m == "lightgbm":
                        m_kwargs = {"n_estimators": 30}
                    elif m == "deepar":
                        m_kwargs = {"epochs": 2, "batch_size": 16, "num_samples": 20}
                    elif m == "tft":
                        m_kwargs = {"epochs": 2, "batch_size": 16}

                    eval_res = cls.evaluate_model_on_series(
                        dataset_id=dataset_id,
                        series_id=s_id,
                        model_name=m,
                        horizon=h,
                        series_df=series_slice,
                        mapping=mapping,
                        n_folds=n_folds,
                        model_kwargs=m_kwargs,
                    )
                    series_evaluations.append(eval_res)

        total_duration = round((time.time() - start_time) * 1000, 2)

        # Build Comparison Tables and Best Model Determinations
        comparison_data = cls._build_comparison_summary(
            dataset_id=dataset_id,
            series_evaluations=series_evaluations,
            models=target_models,
            horizons=target_horizons,
            total_duration_ms=total_duration
        )

        # Attach complete scope metadata
        comparison_data["scope"] = {
            "dataset_id": dataset_id,
            "store_id": store_id,
            "category": category,
            "item_id": item_id,
            "series_ids": target_series,
            "horizons": target_horizons,
            "models": target_models,
        }

        # Cache results - use compound key to support multiple scopes per dataset
        scope_parts = [
            f"store:{store_id}" if store_id else "",
            f"cat:{category}" if category else "",
            f"item:{item_id}" if item_id else "",
            f"series:{','.join(sorted(target_series[:5]))}" if target_series else "",
            f"horizons:{','.join(str(h) for h in sorted(target_horizons))}"
        ]
        scope_key = "|".join([p for p in scope_parts if p])
        _cache_key = f"{dataset_id}|{scope_key}"
        EVALUATION_CACHE[_cache_key] = comparison_data
        comparison_data["scope_key"] = scope_key

        try:
            from ..db.mongo import MongoRepository
            saved = MongoRepository.save_evaluation_comparison(dataset_id, comparison_data, scope_key=scope_key)
            if not saved:
                logger.warning(f"MongoRepository.save_evaluation_comparison returned False for dataset_id={dataset_id}")
        except Exception as ex:
            logger.warning(f"Failed to persist evaluation comparison to MongoDB for dataset_id={dataset_id}: {ex}")

        return comparison_data

    @classmethod
    def _build_comparison_summary(
        cls,
        dataset_id: str,
        series_evaluations: List[Dict[str, Any]],
        models: List[str],
        horizons: List[int],
        total_duration_ms: float
    ) -> Dict[str, Any]:
        """
        Aggregate series-level evaluations into Model x Horizon benchmark matrices
        and determine rankings without hardcoding or fabricating winners.
        """
        successful_evals = [e for e in series_evaluations if e.get("status") == "SUCCESS"]

        # Table 1 & Table 2: Model x Horizon matrices
        model_horizon_mape: Dict[str, Dict[str, Optional[float]]] = {}
        model_horizon_rmse: Dict[str, Dict[str, Optional[float]]] = {}

        for m in models:
            model_horizon_mape[m] = {}
            model_horizon_rmse[m] = {}
            for h in horizons:
                h_str = f"{h}D"
                matches = [e for e in successful_evals if e["model"] == m and e["horizon"] == h]
                if matches:
                    # Sample-weighted MAPE across series: weight by valid non-zero observations
                    valid_items = [e for e in matches if e.get("mape") is not None]
                    total_valid_obs = sum(e.get("mape_valid_count", e.get("sample_count", 1)) for e in valid_items)
                    if total_valid_obs > 0:
                        weighted_mape = sum(
                            e["mape"] * e.get("mape_valid_count", e.get("sample_count", 1))
                            for e in valid_items
                        ) / total_valid_obs
                        avg_mape = round(float(weighted_mape), 2)
                    else:
                        avg_mape = None

                    # Sample-weighted RMSE: pooled mean squared error weighted by sample count
                    rmse_items = [e for e in matches if e.get("rmse") is not None]
                    total_samples = sum(e.get("sample_count", 1) for e in rmse_items)
                    if total_samples > 0:
                        pooled_mse = sum(
                            (float(e["rmse"]) ** 2) * e.get("sample_count", 1)
                            for e in rmse_items
                        ) / total_samples
                        avg_rmse = round(float(np.sqrt(pooled_mse)), 2)
                    else:
                        avg_rmse = None

                    model_horizon_mape[m][h_str] = avg_mape
                    model_horizon_rmse[m][h_str] = avg_rmse
                else:
                    model_horizon_mape[m][h_str] = None
                    model_horizon_rmse[m][h_str] = None

        # Determine Best Model per Horizon
        best_per_horizon: Dict[str, Any] = {}
        for h in horizons:
            h_str = f"{h}D"
            candidates = []
            for m in models:
                m_val = model_horizon_mape[m].get(h_str)
                r_val = model_horizon_rmse[m].get(h_str)
                if m_val is not None:
                    candidates.append({"model": m, "mape": m_val, "rmse": r_val})

            if candidates:
                # Sort ascending by MAPE (lower is better), tie-breaker RMSE
                candidates.sort(key=lambda x: (x["mape"], x["rmse"] or 999999))
                best = candidates[0]
                # Check for tie/near-tie (within 0.2% MAPE)
                ties = [c["model"] for c in candidates if abs(c["mape"] - best["mape"]) <= 0.2]
                best_per_horizon[h_str] = {
                    "best_model": best["model"],
                    "mape": best["mape"],
                    "rmse": best["rmse"],
                    "is_tie": len(ties) > 1,
                    "tied_models": ties if len(ties) > 1 else []
                }
            else:
                best_per_horizon[h_str] = None

        # Overall Best Model across all evaluated horizons (average MAPE across common evaluated horizons)
        evaluated_h_strs = [
            f"{h}D" for h in horizons
            if any(model_horizon_mape[m].get(f"{h}D") is not None for m in models)
        ]
        model_overall_scores = []
        for m in models:
            scores = [
                model_horizon_mape[m][h_str]
                for h_str in evaluated_h_strs
                if model_horizon_mape[m].get(h_str) is not None
            ]
            if scores and len(scores) == len(evaluated_h_strs):
                model_overall_scores.append({
                    "model": m,
                    "overall_mape": round(float(np.mean(scores)), 2),
                    "horizons_covered": len(scores),
                    "evaluated_horizons": evaluated_h_strs,
                })

        model_overall_scores.sort(key=lambda x: x["overall_mape"])
        best_overall = model_overall_scores[0] if model_overall_scores else None

        # Rank series-level evaluations
        ranked_series_evals = []
        for e in successful_evals:
            ranked_series_evals.append({
                "series_id": e["series_id"],
                "model": e["model"],
                "horizon": f"{e['horizon']}D",
                "mape": e["mape"],
                "rmse": e["rmse"],
                "folds_evaluated": e["fold_count"],
                "sample_count": e["sample_count"],
            })
        ranked_series_evals.sort(key=lambda x: (x["series_id"], x["horizon"], x["mape"] if x["mape"] is not None else 999999))

        return {
            "dataset_id": dataset_id,
            "models_evaluated": models,
            "horizons_evaluated": evaluated_h_strs,
            "total_series_evaluated": len(set(e["series_id"] for e in series_evaluations)),
            "total_evaluations_count": len(series_evaluations),
            "execution_duration_ms": total_duration_ms,
            "table_1_model_x_horizon_mape": model_horizon_mape,
            "table_2_model_x_horizon_rmse": model_horizon_rmse,
            "table_3_series_evaluations": ranked_series_evals,
            "best_per_horizon": best_per_horizon,
            "best_model_overall": best_overall,
            "split_policy": "80:20_chronological",
            "series_details": series_evaluations,
        }

    @classmethod
    def get_evaluation_for_dataset(
        cls,
        dataset_id: str,
        store_id: Optional[str] = None,
        category: Optional[str] = None,
        item_id: Optional[str] = None,
        series_id: Optional[str] = None,
        horizon: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve cached evaluation matching requested scope if available."""
        exact_matches = []
        partial_matches = []

        for k, res in reversed(list(EVALUATION_CACHE.items())):
            if k == dataset_id:
                partial_matches.append(res)
                continue
            if not str(k).startswith(f"{dataset_id}|") and str(k) != dataset_id:
                continue
            sc = res.get("scope", {}) if isinstance(res, dict) else {}

            # Strict mismatch checks if cache entry was explicitly scoped to a different entity
            if store_id and sc.get("store_id") is not None and sc.get("store_id") != store_id:
                continue
            if category and sc.get("category") is not None and sc.get("category") != category:
                continue
            if item_id and sc.get("item_id") is not None and sc.get("item_id") != item_id:
                continue

            # Check if requested series was evaluated in this cache entry
            series_in_cache = False
            if series_id:
                cached_series = sc.get("series_ids") or [
                    e.get("series_id") for e in res.get("table_3_series_evaluations", [])
                ]
                if cached_series and series_id not in cached_series:
                    continue
                series_in_cache = True

            # Check horizon
            if horizon:
                cached_horizons = sc.get("horizons") or [
                    int(h.replace("D", "")) for h in res.get("horizons_evaluated", []) if "D" in str(h)
                ]
                if cached_horizons and horizon not in cached_horizons:
                    continue

            # Prioritize exact store and series matches
            if store_id and sc.get("store_id") == store_id:
                exact_matches.append(res)
            elif series_in_cache:
                exact_matches.append(res)
            else:
                partial_matches.append(res)

        if exact_matches:
            return exact_matches[0]
        if partial_matches:
            return partial_matches[0]

        try:
            from ..db.mongo import MongoRepository
            # Check MongoDB for matching evaluation document
            db_res = MongoRepository.get_evaluation_comparison(dataset_id)
            if db_res:
                # Populate in-memory cache so subsequent reads are immediate
                res_scope_key = db_res.get("scope_key") or "default"
                EVALUATION_CACHE[f"{dataset_id}|{res_scope_key}"] = db_res
                return db_res
        except Exception as ex:
            logger.warning(f"Error fetching evaluation from MongoDB for dataset_id={dataset_id}: {ex}")

        return None

    @classmethod
    def get_best_model_for_series_horizon(
        cls,
        dataset_id: str,
        series_id: str,
        horizon: int,
        store_id: Optional[str] = None,
        category: Optional[str] = None,
        item_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Return the empirically best model for a specific dataset, series, and horizon.
        If no evaluation exists, returns None.
        """
        cached = cls.get_evaluation_for_dataset(
            dataset_id,
            store_id=store_id,
            category=category,
            item_id=item_id,
            series_id=series_id,
            horizon=horizon,
        )
        if not cached:
            cached = cls.get_evaluation_for_dataset(dataset_id, series_id=series_id)
        if not cached:
            return None

        # 1. Check series-specific evaluations
        h_str = f"{horizon}D"
        series_matches = [
            e for e in cached.get("table_3_series_evaluations", [])
            if e["series_id"] == series_id and e["horizon"] == h_str and e.get("mape") is not None
        ]
        if series_matches:
            series_matches.sort(key=lambda x: x["mape"])
            return series_matches[0]["model"]

        # 2. Check dataset-level horizon winner
        h_best = cached.get("best_per_horizon", {}).get(h_str)
        if h_best and h_best.get("best_model"):
            return h_best["best_model"]

        # 3. Overall best model
        overall = cached.get("best_model_overall")
        if overall and overall.get("model"):
            return overall["model"]

        return None
