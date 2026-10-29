"""
Forecasting Performance Monitoring & Drift Detection (Phase 9)
ForecastIQ Backend

Tracks:
- Historical MAPE and RMSE across chronological backtest folds and evaluation windows.
- Compares recent window accuracy against baseline history.
- Flags performance drift and emits actionable retraining review alerts.

Statuses:
- HEALTHY
- WATCH
- ACCURACY DRIFT
- INSUFFICIENT DATA
"""
from typing import Dict, Any, List, Optional
from ..data.schema import MonitoringReport
from ..evaluation.backtesting import BacktestingEngine

# In-memory monitoring cache: dataset_id -> MonitoringReport dict
MONITORING_CACHE: Dict[str, Dict[str, Any]] = {}

# Configurable drift thresholds
DRIFT_WATCH_THRESHOLD_PCT = 10.0
DRIFT_ALERT_THRESHOLD_PCT = 25.0


class MonitoringTracker:
    """
    Tracks model performance over time and detects accuracy degradation.
    Evaluates real chronological backtest evidence per dataset, series, model, and horizon scope.
    """

    @staticmethod
    def _make_scope_key(
        dataset_id: str,
        series_id: Optional[str] = None,
        store_id: Optional[str] = None,
        category: Optional[str] = None,
        item_id: Optional[str] = None,
        model: Optional[str] = None,
        horizon: Optional[int] = None,
    ) -> str:
        s_id = series_id or "_"
        st_id = store_id or "_"
        cat = category or "_"
        it_id = item_id or "_"
        m = (model or "_").lower()
        h = f"{horizon}D" if horizon else "_"
        return f"{dataset_id}:{st_id}:{cat}:{it_id}:{s_id}:{m}:{h}"

    @classmethod
    def evaluate_monitoring_status(
        cls,
        dataset_id: str,
        backtest_summary: Optional[Dict[str, Any]] = None,
        watch_threshold: float = DRIFT_WATCH_THRESHOLD_PCT,
        alert_threshold: float = DRIFT_ALERT_THRESHOLD_PCT,
        series_id: Optional[str] = None,
        store_id: Optional[str] = None,
        category: Optional[str] = None,
        item_id: Optional[str] = None,
        model: Optional[str] = None,
        horizon: Optional[int] = None,
    ) -> MonitoringReport:
        """
        Evaluate chronological accuracy across backtesting folds to detect potential performance decay.
        Scoping rules:
        - When series_id, model, or horizon is provided, filter evaluations strictly to that scope.
        - If 'automatic' or 'best' model is selected, resolve the winning model for the scope.
        - Never label a model HEALTHY without at least 2 distinct evaluation folds of empirical evidence.
        - If fewer than 2 folds exist, return honest 'INSUFFICIENT DATA' or 'NOT EVALUATED'.
        """
        summary = backtest_summary or BacktestingEngine.get_evaluation_for_dataset(
            dataset_id=dataset_id,
            store_id=store_id,
            category=category,
            item_id=item_id,
            series_id=series_id,
            horizon=horizon,
        )

        scope_dict = {
            "dataset_id": dataset_id,
            "series_id": series_id,
            "store_id": store_id,
            "category": category,
            "item_id": item_id,
            "model": model,
            "horizon": horizon,
        }

        if not summary:
            return MonitoringReport(
                dataset_id=dataset_id,
                status="INSUFFICIENT DATA",
                retraining_alert=None,
                is_alert=False,
                models_tracked=[],
                details=[{"message": "No backtesting evaluations available yet for monitoring this scope."}],
                series_id=series_id,
                store_id=store_id,
                category=category,
                item_id=item_id,
                horizon=horizon,
                scope=scope_dict,
            )

        series_details = summary.get("series_details", [])
        models_tracked = summary.get("models_evaluated", [])

        # If a specific model is requested, check if it's 'automatic'
        target_model = (model or "").lower()
        if target_model in ["automatic", "auto", "best", ""]:
            # Pick best model for horizon if present in summary
            h_key = f"{horizon}D" if horizon else None
            best_per_horizon = summary.get("best_per_horizon", {})
            if h_key and best_per_horizon.get(h_key):
                target_model = best_per_horizon[h_key].get("best_model", "").lower()
            elif summary.get("best_model_overall"):
                target_model = summary["best_model_overall"].get("model", "").lower()
            else:
                target_model = ""

        # Filter series_details by series_id, model, and horizon
        filtered_series = series_details
        if series_id:
            filtered_series = [s for s in filtered_series if str(s.get("series_id")) == str(series_id)]

        if target_model:
            filtered_series = [s for s in filtered_series if str(s.get("model", "")).lower() == target_model]

        if horizon:
            filtered_series = [s for s in filtered_series if s.get("horizon") == horizon]

        # If after filtering no series remain, check if we had any records matching just series/model
        if not filtered_series:
            # If the summary had no series evaluations at all across the dataset, status is INSUFFICIENT DATA
            if not series_details:
                status_val = "INSUFFICIENT DATA"
                msg = "No backtesting evaluations available yet for monitoring."
            else:
                status_val = "NOT EVALUATED"
                msg = f"No backtesting evaluations found for series={series_id or 'all'}, model={target_model or 'all'}, horizon={horizon or 'all'}D."

            return MonitoringReport(
                dataset_id=dataset_id,
                status=status_val,
                retraining_alert=None,
                is_alert=False,
                models_tracked=models_tracked,
                details=[{"message": msg}],
                series_id=series_id,
                store_id=store_id,
                category=category,
                item_id=item_id,
                horizon=horizon,
                scope=scope_dict,
            )

        # Collect chronological fold MAPEs across matching series
        fold_mapes: Dict[int, List[float]] = {}
        for s in filtered_series:
            folds = s.get("folds", [])
            for f in folds:
                f_num = f.get("fold", 1)
                f_mape = f.get("mape")
                if f_mape is not None and f.get("status") == "SUCCESS":
                    fold_mapes.setdefault(f_num, []).append(float(f_mape))

        if len(fold_mapes) < 2:
            # Need at least 2 distinct folds to compute drift between baseline and recent
            first_fold_values = fold_mapes.get(1, [])
            baseline_mape = round(float(sum(first_fold_values) / len(first_fold_values)), 2) if first_fold_values else None
            return MonitoringReport(
                dataset_id=dataset_id,
                status="INSUFFICIENT DATA" if len(fold_mapes) == 0 else "INSUFFICIENT DATA",
                baseline_mape=baseline_mape,
                recent_mape=baseline_mape,
                mape_drift_pct=None,
                retraining_alert=None,
                is_alert=False,
                models_tracked=[target_model] if target_model else models_tracked,
                details=[{"message": f"Only {len(fold_mapes)} evaluation fold(s) available for this scope. At least 2 distinct chronological folds are required to measure performance drift."}],
                series_id=series_id,
                store_id=store_id,
                category=category,
                item_id=item_id,
                horizon=horizon,
                scope=scope_dict,
            )

        sorted_fold_nums = sorted(fold_mapes.keys())
        first_fold_num = sorted_fold_nums[0]
        latest_fold_num = sorted_fold_nums[-1]

        base_vals = fold_mapes[first_fold_num]
        recent_vals = fold_mapes[latest_fold_num]

        baseline_mape = round(float(sum(base_vals) / len(base_vals)), 2) if base_vals else 0.0
        recent_mape = round(float(sum(recent_vals) / len(recent_vals)), 2) if recent_vals else 0.0

        if baseline_mape > 0:
            drift_pct = round(((recent_mape - baseline_mape) / baseline_mape) * 100.0, 2)
        else:
            drift_pct = 0.0

        if drift_pct >= alert_threshold:
            status = "ACCURACY DRIFT"
            retraining_alert = f"Prediction error increased by {drift_pct}% from baseline fold {first_fold_num} to fold {latest_fold_num}. Model retraining or recalibration recommended."
            is_alert = True
        elif drift_pct >= watch_threshold:
            status = "WATCH"
            retraining_alert = f"Moderate error increase ({drift_pct}%) observed between baseline and recent folds. Continue monitoring next cycle."
            is_alert = False
        else:
            status = "HEALTHY"
            retraining_alert = None
            is_alert = False

        details = [
            {
                "fold": first_fold_num,
                "label": "Baseline Window",
                "avg_mape": baseline_mape,
                "sample_evaluations": len(base_vals),
            },
            {
                "fold": latest_fold_num,
                "label": "Most Recent Window",
                "avg_mape": recent_mape,
                "sample_evaluations": len(recent_vals),
            }
        ]

        report = MonitoringReport(
            dataset_id=dataset_id,
            status=status,
            baseline_mape=baseline_mape,
            recent_mape=recent_mape,
            mape_drift_pct=drift_pct,
            retraining_alert=retraining_alert,
            is_alert=is_alert,
            models_tracked=[target_model] if target_model else models_tracked,
            details=details,
            series_id=series_id,
            store_id=store_id,
            category=category,
            item_id=item_id,
            horizon=horizon,
            scope=scope_dict,
        )

        dumped = report.model_dump()
        cache_key = cls._make_scope_key(
            dataset_id=dataset_id,
            series_id=series_id,
            store_id=store_id,
            category=category,
            item_id=item_id,
            model=model,
            horizon=horizon,
        )
        MONITORING_CACHE[cache_key] = dumped
        MONITORING_CACHE[dataset_id] = dumped

        try:
            from ..db.mongo import MongoRepository
            MongoRepository.save_monitoring_report(dataset_id, dumped)
        except Exception:
            pass

        return report

    @classmethod
    def get_monitoring_report(
        cls,
        dataset_id: str,
        series_id: Optional[str] = None,
        store_id: Optional[str] = None,
        category: Optional[str] = None,
        item_id: Optional[str] = None,
        model: Optional[str] = None,
        horizon: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve cached monitoring report if present in-memory or MongoDB."""
        cache_key = cls._make_scope_key(
            dataset_id=dataset_id,
            series_id=series_id,
            store_id=store_id,
            category=category,
            item_id=item_id,
            model=model,
            horizon=horizon,
        )
        if cache_key in MONITORING_CACHE:
            return MONITORING_CACHE[cache_key]

        if dataset_id in MONITORING_CACHE and not (series_id or model or horizon):
            return MONITORING_CACHE[dataset_id]

        try:
            from ..db.mongo import MongoRepository
            db_res = MongoRepository.get_monitoring_report(dataset_id)
            if db_res:
                MONITORING_CACHE[cache_key] = db_res
                return db_res
        except Exception:
            pass

        return None

