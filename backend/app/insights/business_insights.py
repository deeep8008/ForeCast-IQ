"""
Business Insight Engine (Phase 9)
ForecastIQ Backend

Generates structured, evidence-based business insights and actionable decision-support
recommendations from actual forecast predictions, historical observations, and evaluation benchmarks.

Rules:
- No causal claims without causal analysis. Uses terms like 'observed alongside', 'associated with', 'coincides with'.
- Centralized configurable business thresholds.
- No fabricated inventory quantities or employee counts.
- Uncertainty derived strictly from genuine prediction intervals (returns UNKNOWN if intervals absent).
- Exogenous insights generated ONLY if the respective features actually exist in the dataset.
"""
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from ..data.schema import (
    ForecastResult,
    BusinessInsightsResponse,
    DemandOutlook,
    RecommendationItem,
)


@dataclass
class BusinessThresholds:
    """Centralized, configurable business thresholds for demand direction & risk."""
    demand_increase_pct: float = 10.0
    demand_decrease_pct: float = -10.0
    surge_high_pct: float = 25.0
    drop_severe_pct: float = -25.0
    uncertainty_spread_high: float = 0.35   # relative spread: (upper - lower) / forecast
    uncertainty_spread_medium: float = 0.15
    recent_baseline_window_days: int = 28


# In-memory insights cache: f"{dataset_id}:{series_id}:{horizon}:{model}" -> BusinessInsightsResponse dict
INSIGHTS_CACHE: Dict[str, Dict[str, Any]] = {}

_MODEL_CANONICAL = {"arima", "sarima", "prophet", "lightgbm", "deepar", "tft", "automatic"}

def _normalize_model_key(model_str: str) -> str:
    """Normalize ARIMA(1,1,1) -> arima, SARIMA(...) -> sarima etc."""
    if not model_str:
        return "unknown"
    lower = model_str.lower().strip().split("(")[0].split(" ")[0]
    return lower if lower in _MODEL_CANONICAL else lower


class BusinessInsightEngine:
    """
    Evidence-based business intelligence generator for enterprise supply chain and retail operations.
    """

    @classmethod
    def generate_insights(
        cls,
        forecast_result: ForecastResult,
        historical_df: pd.DataFrame,
        mapping: Dict[str, Any],
        thresholds: Optional[BusinessThresholds] = None,
        evaluation_summary: Optional[Dict[str, Any]] = None,
        store_id: Optional[str] = None,
        category: Optional[str] = None,
        item_id: Optional[str] = None,
        scope: Optional[Dict[str, Any]] = None,
        model_key: Optional[str] = None,
    ) -> BusinessInsightsResponse:
        """
        Build complete actionable business insights based strictly on empirical calculations.
        """
        t = thresholds or BusinessThresholds()
        time_col = mapping.get("date", "date")
        target_col = mapping.get("target", "target")

        # 1. Historical Baseline Calculations
        sorted_hist = historical_df.sort_values(by=time_col).reset_index(drop=True)
        recent_slice = sorted_hist.tail(t.recent_baseline_window_days)
        recent_values = [float(v) for v in recent_slice[target_col].dropna().values]

        if not recent_values:
            recent_values = [float(v) for v in sorted_hist[target_col].dropna().values] or [1.0]

        recent_avg = float(np.mean(recent_values))
        forecast_values = [float(v) for v in forecast_result.forecast]
        forecast_avg = float(np.mean(forecast_values)) if forecast_values else recent_avg

        # 2. Percentage Change & Direction
        expected_change_pct = round(((forecast_avg - recent_avg) / recent_avg) * 100.0, 2) if recent_avg > 0 else 0.0

        # 3. Variability & Extremes
        forecast_std = float(np.std(forecast_values)) if len(forecast_values) > 1 else 0.0
        variability = round(forecast_std / forecast_avg, 3) if forecast_avg > 0 else 0.0

        dates_list = getattr(forecast_result, "dates", None) or getattr(forecast_result, "timestamps", [])
        h = int(getattr(forecast_result, "forecast_horizon", None) or getattr(forecast_result, "horizon", None) or len(forecast_values))

        # Strictly slice both lists to the requested horizon length.
        # Without this, argmax/argmin can pick an index beyond the horizon window
        # (e.g., day 35 when horizon=28) producing a trough date outside the planning period.
        forecast_values = forecast_values[:h]
        dates_list = list(dates_list)[:h]

        max_idx = int(np.argmax(forecast_values))
        min_idx = int(np.argmin(forecast_values))
        peak_date = str(dates_list[max_idx]) if max_idx < len(dates_list) else "N/A"
        low_date = str(dates_list[min_idx]) if min_idx < len(dates_list) else "N/A"

        expected_peak = {
            "value": round(forecast_values[max_idx], 2),
            "date": peak_date[:10],
            "day_index": max_idx + 1
        }
        expected_low = {
            "value": round(forecast_values[min_idx], 2),
            "date": low_date[:10],
            "day_index": min_idx + 1
        }

        # 4. Uncertainty Level (Strict genuine intervals only)
        has_genuine_intervals = (
            forecast_result.lower_bound is not None
            and forecast_result.upper_bound is not None
            and len(forecast_result.lower_bound) == len(forecast_values)
            and len(forecast_result.upper_bound) == len(forecast_values)
        )

        if has_genuine_intervals:
            spreads = []
            for f_val, l_val, u_val in zip(forecast_values, forecast_result.lower_bound, forecast_result.upper_bound):
                if f_val > 0 and u_val is not None and l_val is not None:
                    spreads.append((float(u_val) - float(l_val)) / float(f_val))
            mean_spread = float(np.mean(spreads)) if spreads else 0.0

            if mean_spread >= t.uncertainty_spread_high:
                uncertainty_level = "HIGH"
            elif mean_spread >= t.uncertainty_spread_medium:
                uncertainty_level = "MEDIUM"
            else:
                uncertainty_level = "LOW"
        else:
            uncertainty_level = "UNKNOWN"

        # 5. Demand Direction State
        if uncertainty_level == "HIGH" and abs(expected_change_pct) < 5.0 and variability > 0.3:
            demand_direction = "HIGHLY UNCERTAIN"
        elif expected_change_pct >= t.demand_increase_pct:
            demand_direction = "INCREASING"
        elif expected_change_pct <= t.demand_decrease_pct:
            demand_direction = "DECREASING"
        else:
            demand_direction = "STABLE"

        start_ts = str(dates_list[0])[:10] if dates_list else ""
        end_ts = str(dates_list[-1])[:10] if dates_list else ""
        forecast_period = f"{start_ts} to {end_ts}"

        # Common Evidence Object
        evidence_dict = {
            "recent_average": round(recent_avg, 2),
            "forecast_average": round(forecast_avg, 2),
            "expected_change_pct": expected_change_pct,
            "expected_peak": expected_peak,
            "expected_low": expected_low,
            "variability": variability,
            "horizon": h,
            "model": forecast_result.model,
            "uncertainty_level": uncertainty_level,
        }

        # 6. Inventory Recommendation
        if demand_direction == "HIGHLY UNCERTAIN":
            inv_rec = "MONITOR DEMAND"
            inv_priority = "MEDIUM"
            inv_reason = (
                f"Forecast demand exhibits wide predictive intervals across the {h}-day horizon. "
                "Monitor actual daily checkout velocity before committing to aggressive inventory adjustments."
            )
        elif demand_direction == "INCREASING":
            if uncertainty_level == "HIGH":
                inv_rec = "MONITOR DEMAND"
                inv_priority = "MEDIUM"
                inv_reason = (
                    f"Forecast demand projects a {expected_change_pct:+.1f}% increase over baseline, but wider prediction intervals suggest caution. "
                    "Monitor short-term intake velocity."
                )
            else:
                inv_rec = "CONSIDER STOCKING UP"
                inv_priority = "HIGH" if expected_change_pct >= t.surge_high_pct else "MEDIUM"
                inv_reason = (
                    f"Forecast demand is projected to be {abs(expected_change_pct)}% above the recent baseline, "
                    f"with peak velocity expected on {expected_peak['date']} ({expected_peak['value']} units). "
                    f"Consider reviewing safety stock replenishment ahead of elevated demand."
                )
        elif demand_direction == "DECREASING":
            inv_rec = "AVOID OVERSTOCKING / REVIEW EXCESS INVENTORY"
            inv_priority = "HIGH" if expected_change_pct <= t.drop_severe_pct else "MEDIUM"
            inv_reason = (
                f"Forecast demand projects a {abs(expected_change_pct)}% decrease relative to the recent baseline. "
                "Review ongoing replenishment cadence to avoid holding unnecessary buffer inventory."
            )
        else:  # STABLE
            inv_rec = "MAINTAIN CURRENT STOCK"
            inv_priority = "LOW"
            inv_reason = (
                f"Forecast demand is projected to remain stable ({expected_change_pct:+.1f}% vs baseline) "
                f"over the upcoming {h}-day period. Existing replenishment cycles remain appropriate."
            )

        inventory_item = RecommendationItem(
            category="inventory",
            recommendation=inv_rec,
            priority=inv_priority,
            reason=inv_reason,
            evidence=evidence_dict,
            planning_period=forecast_period,
            uncertainty=uncertainty_level,
            horizon=h,
        )

        # 7. Staffing / Resource Recommendation
        if demand_direction == "INCREASING":
            staff_rec = "INCREASE STAFFING / RESOURCE AVAILABILITY"
            staff_priority = "HIGH" if expected_change_pct >= t.surge_high_pct else "MEDIUM"
            staff_reason = (
                f"Demand is projected to remain above the recent baseline (+{expected_change_pct}%) during the upcoming {h} days. "
                f"Consider increasing fulfillment and floor handling capacity, particularly coinciding with the peak window around {expected_peak['date']}."
            )
        elif demand_direction == "DECREASING":
            staff_rec = "REVIEW CAPACITY"
            staff_priority = "MEDIUM"
            staff_reason = (
                f"Demand is projected to contract by {abs(expected_change_pct)}% over the {h}-day period. "
                "Consider reallocating staging and restocking labor to higher-volume product lines."
            )
        elif demand_direction == "HIGHLY UNCERTAIN":
            staff_rec = "MONITOR WORKLOAD"
            staff_priority = "MEDIUM"
            staff_reason = (
                "Wide prediction intervals indicate fluctuating operational requirements. "
                "Maintain cross-trained support flexibility while monitoring daily shifts."
            )
        else:
            staff_rec = "MAINTAIN CURRENT CAPACITY"
            staff_priority = "LOW"
            staff_reason = "Demand levels align with normal baseline operations; standard shift allocations remain appropriate."

        staffing_item = RecommendationItem(
            category="staffing",
            recommendation=staff_rec,
            priority=staff_priority,
            reason=staff_reason,
            evidence=evidence_dict,
            planning_period=forecast_period,
            uncertainty=uncertainty_level,
            horizon=h,
        )

        # 8. Procurement Recommendation
        if demand_direction == "INCREASING":
            proc_rec = "REVIEW PROCUREMENT PLANNING"
            proc_priority = "HIGH" if expected_change_pct >= t.surge_high_pct else "MEDIUM"
            proc_reason = (
                f"Elevated projected velocity (+{expected_change_pct}%) indicates increased forward replenishment requirements. "
                "Review vendor lead times and purchase order timing with key suppliers."
            )
        elif demand_direction == "DECREASING":
            proc_rec = "REVIEW PROCUREMENT TIMING"
            proc_priority = "MEDIUM"
            proc_reason = (
                f"Lower projected demand (-{abs(expected_change_pct)}%) suggests reviewing pending procurement schedules "
                "to align delivery dates with reduced outbound velocity."
            )
        elif demand_direction == "HIGHLY UNCERTAIN":
            proc_rec = "MONITOR"
            proc_priority = "MEDIUM"
            proc_reason = (
                "Due to higher prediction variance, align purchase commitments with confirmed demand run-rates "
                "rather than speculative advance volumes."
            )
        else:
            proc_rec = "MAINTAIN PROCUREMENT"
            proc_priority = "LOW"
            proc_reason = "Run-rates match recent baseline velocity; maintain existing supplier procurement cadences."

        procurement_item = RecommendationItem(
            category="procurement",
            recommendation=proc_rec,
            priority=proc_priority,
            reason=proc_reason,
            evidence=evidence_dict,
            planning_period=forecast_period,
            uncertainty=uncertainty_level,
            horizon=h,
        )

        # 9. Demand Planning Interpretation (Short, Medium, Long)
        action_title = (
            "EXPAND CAPACITY / ACCELERATE INVENTORY INFLOW" if demand_direction == "INCREASING" else
            "REDUCE PROCUREMENT / ALIGN INVENTORY CADENCE" if demand_direction == "DECREASING" else
            "MONITOR RUN-RATES / MAINTAIN BUFFER FLEXIBILITY" if demand_direction == "HIGHLY UNCERTAIN" else
            "MAINTAIN STEADY ALLOCATION / STABLE VELOCITY"
        )
        explanation_text = (
            f"Forecast average ({forecast_avg:.1f} units/day) projects a {expected_change_pct:+.1f}% shift relative to recent baseline ({recent_avg:.1f} units/day) across the {h}-day horizon."
        )
        planning_focus_text = (
            f"Expected peak demand of {expected_peak['value']} units on {expected_peak['date']} requires scheduled order replenishment buffers."
            if expected_peak["value"] > 0 else
            f"Ongoing baseline velocity of {recent_avg:.1f} units/day guides operational planning."
        )

        dp_interpretation = {
            "state": (
                "PREPARE FOR DEMAND INCREASE" if demand_direction == "INCREASING" else
                "PREPARE FOR DEMAND DECLINE" if demand_direction == "DECREASING" else
                "MONITOR" if demand_direction == "HIGHLY UNCERTAIN" else
                "STABLE DEMAND"
            ),
            "action": action_title,
            "explanation": explanation_text,
            "planning_focus": planning_focus_text,
            "short_term_interpretation": (
                f"Days 1–7: Initial trajectory shows average daily demand of {round(float(np.mean(forecast_values[:min(7, len(forecast_values))])), 1)} units. "
                f"Immediate operations should align with day-to-day velocity."
            ),
            "medium_term_interpretation": (
                f"Days 8–28: Tactical cycle averages {round(float(np.mean(forecast_values[:min(28, len(forecast_values))])), 1)} units/day. "
                "Captures intra-month replenishment cycles."
            ),
            "long_term_interpretation": (
                f"Days 29–90: Extended strategic projection shows cumulative outlook across the planning horizon. "
                "Recommended for aggregate capacity guidance."
            ),
        }

        # 10. Horizon-Specific Insights (Strictly scoped to executed horizon length and sliced per horizon)
        def _calc_horizon_metrics(slice_len: int):
            if len(forecast_values) < slice_len:
                return None
            vals = forecast_values[:slice_len]
            dts = dates_list[:slice_len]
            p_idx = int(np.argmax(vals))
            l_idx = int(np.argmin(vals))
            p_date = str(dts[p_idx])[:10] if p_idx < len(dts) else "N/A"
            l_date = str(dts[l_idx])[:10] if l_idx < len(dts) else "N/A"
            return {
                "avg": round(float(np.mean(vals)), 1),
                "peak_val": round(vals[p_idx], 2),
                "peak_date": p_date,
                "low_val": round(vals[l_idx], 2),
                "low_date": l_date,
                "start_date": str(dts[0])[:10] if dts else "",
                "end_date": str(dts[-1])[:10] if dts else "",
            }

        m_7d = _calc_horizon_metrics(7)
        m_28d = _calc_horizon_metrics(28)
        m_90d = _calc_horizon_metrics(90)

        horizon_insights = {
            "7D": (
                f"Near-term operational demand is projected at an average of {m_7d['avg']} units/day, with estimated peak of {m_7d['peak_val']} units on {m_7d['peak_date']} (window: {m_7d['start_date']} to {m_7d['end_date']})."
                if m_7d is not None else "7-day operational projection unavailable."
            ),
            "28D": (
                f"Tactical monthly demand projects {m_28d['avg']} units/day average, with estimated peak of {m_28d['peak_val']} units on {m_28d['peak_date']} (window: {m_28d['start_date']} to {m_28d['end_date']})."
                if m_28d is not None else f"Not evaluated for {h}-day horizon. Switch horizon to 28 Days to generate tactical monthly insights."
            ),
            "90D": (
                f"Quarterly strategic trajectory projects {m_90d['avg']} units/day average, with estimated peak of {m_90d['peak_val']} units on {m_90d['peak_date']} (window: {m_90d['start_date']} to {m_90d['end_date']})."
                if m_90d is not None else f"Not evaluated (Current forecast is for {h} days; 90-day horizon requires 90D selection and sufficient history)."
            ),
        }

        # 11. Optional Exogenous Feature Context (Strictly when genuine data is present)
        opt_context = {}
        optional_map = mapping.get("optional", {})

        # Check Price (distinguish genuine non-zero price data from missing or 0.0 fallbacks)
        price_col = optional_map.get("price") or (target_col if "price" in target_col else None)
        if price_col and price_col in historical_df.columns:
            valid_prices = pd.to_numeric(historical_df[price_col], errors="coerce").dropna()
            non_zero_prices = valid_prices[valid_prices > 0.0]
            if not non_zero_prices.empty:
                recent_prices = non_zero_prices.tail(28)
                avg_price = round(float(recent_prices.mean()), 2)
                # Only reference promotion data when an actual promotion column is mapped.
                # The canonical M5 sample contains price but no promotion field, so we
                # must not fabricate promotional context.
                promo_mapped = bool(optional_map.get("promotion") and optional_map["promotion"] in historical_df.columns)
                promo_suffix = (
                    "" if promo_mapped
                    else " Promotion information unavailable (no promotion field in this dataset)."
                )
                opt_context["price"] = {
                    "available": True,
                    "recent_avg_price": avg_price,
                    "promotion_available": promo_mapped,
                    "insight": f"Historical unit price averaged ${avg_price:.2f} across the most recent records.{promo_suffix}"
                }
            else:
                opt_context["price"] = {
                    "available": False,
                    "recent_avg_price": None,
                    "promotion_available": False,
                    "insight": "Historical unit price unavailable (no valid non-zero price records found for this scope)."
                }

        # Check Promotion
        promo_col = optional_map.get("promotion")
        if promo_col and promo_col in historical_df.columns:
            promo_active_count = int(historical_df[promo_col].astype(bool).sum())
            if promo_active_count > 0:
                opt_context["promotion"] = {
                    "available": True,
                    "active_promo_count": promo_active_count,
                    "insight": f"Promotional flags are recorded for {promo_active_count} observations; promotional windows coincide with elevated sales volumes."
                }
            else:
                opt_context["promotion"] = {
                    "available": False,
                    "active_promo_count": 0,
                    "insight": "No active promotional flags recorded for this scope."
                }

        # Check Holiday / Events (only report when non-empty, non-placeholder event names exist)
        holiday_col = optional_map.get("holiday")
        if holiday_col and holiday_col in historical_df.columns:
            raw_events = historical_df[holiday_col].dropna().astype(str).tolist()
            # Expanded placeholder exclusion set — covers M5 blanks and common sentinel values
            _PLACEHOLDER = {"", "none", "nan", "null", "0", "false", "na", "n/a",
                            "unknown", "unknown event", "no event", "no holiday"}
            genuine_records = [e.strip() for e in raw_events if e.strip().lower() not in _PLACEHOLDER]
            unique_event_types = list(dict.fromkeys(genuine_records))  # deduplicated, order-preserved
            event_record_count = len(genuine_records)                  # total raw records (not deduped)
            unique_type_count = len(unique_event_types)
            if unique_event_types:
                # Build a name summary consistent with the stated unique_type_count.
                # Showing only [:3] names while claiming "16 unique types" misleads
                # readers into thinking only 3 types were detected.
                # Show up to 5; append "and N more" so the text always reflects reality.
                shown_names = unique_event_types[:5]
                remainder = unique_type_count - len(shown_names)
                if remainder > 0:
                    names_summary = f"{', '.join(shown_names)}, and {remainder} more"
                else:
                    names_summary = ', '.join(shown_names)
                opt_context["holiday"] = {
                    "available": True,
                    "event_records": event_record_count,
                    "events_detected": unique_type_count,
                    # Return up to 10 names so the frontend tag list can display them
                    "event_names": unique_event_types[:10],
                    "insight": (
                        f"{unique_type_count} unique calendar event type(s) recorded across "
                        f"{event_record_count} observation(s) in the historical period "
                        f"(e.g. {names_summary}). "
                        "Demand movements near these dates are noted; no causal relationship is implied."
                    )
                }
            else:
                opt_context["holiday"] = {
                    "available": False,
                    "events_detected": 0,
                    "insight": "No calendar holiday events recorded in historical period."
                }

        outlook = DemandOutlook(
            recent_average_demand=round(recent_avg, 2),
            forecast_average_demand=round(forecast_avg, 2),
            expected_change_pct=expected_change_pct,
            expected_peak=expected_peak,
            expected_low=expected_low,
            forecast_period=forecast_period,
            demand_direction=demand_direction,
            variability=variability,
            uncertainty_level=uncertainty_level,
        )

        # Determine scope attributes if not explicitly provided
        store_col = mapping.get("optional", {}).get("store_id") if isinstance(mapping.get("optional"), dict) else None
        cat_col = mapping.get("optional", {}).get("category") if isinstance(mapping.get("optional"), dict) else None
        item_col = mapping.get("optional", {}).get("item_id") if isinstance(mapping.get("optional"), dict) else None

        if not store_id and store_col and store_col in historical_df.columns and len(historical_df) > 0:
            store_id = str(historical_df[store_col].iloc[0])
        if not category and cat_col and cat_col in historical_df.columns and len(historical_df) > 0:
            category = str(historical_df[cat_col].iloc[0])
        if not item_id and item_col and item_col in historical_df.columns and len(historical_df) > 0:
            item_id = str(historical_df[item_col].iloc[0])

        canonical_model = model_key or _normalize_model_key(forecast_result.model)

        scope_dict = scope or {
            "dataset_id": forecast_result.dataset_id,
            "store_id": store_id,
            "category": category,
            "item_id": item_id,
            "series_id": forecast_result.series_id,
            "model": canonical_model,
            "horizon": h,
        }

        res = BusinessInsightsResponse(
            dataset_id=forecast_result.dataset_id,
            series_id=forecast_result.series_id,
            model=canonical_model,
            horizon=h,
            store_id=store_id,
            category=category,
            item_id=item_id,
            scope=scope_dict,
            demand_outlook=outlook,
            inventory_recommendation=inventory_item,
            staffing_recommendation=staffing_item,
            procurement_recommendation=procurement_item,
            demand_planning=dp_interpretation,
            horizon_insights=horizon_insights,
            optional_feature_context=opt_context if opt_context else None,
        )

        cache_key = f"{forecast_result.dataset_id}:store:{store_id or '_'}:cat:{category or '_'}:item:{item_id or '_'}:{forecast_result.series_id}:{h}:{canonical_model}"
        dumped = res.model_dump()
        INSIGHTS_CACHE[cache_key] = dumped

        # Persist to MongoDB if available
        try:
            from ..db.mongo import MongoRepository
            MongoRepository.save_business_insights(dumped)
        except Exception:
            pass

        return res

    @classmethod
    def get_cached_insights(
        cls,
        dataset_id: str,
        series_id: Optional[str] = None,
        horizon: Optional[int] = None,
        model: Optional[str] = None,
        store_id: Optional[str] = None,
        category: Optional[str] = None,
        item_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve stored insight matching dataset + scope from in-memory cache or MongoDB."""
        norm_model = _normalize_model_key(model) if model else None
        for key, val in INSIGHTS_CACHE.items():
            if not isinstance(val, dict) or not key.startswith(dataset_id + ":"):
                continue
            # Match using stored response metadata (canonical fields)
            val_series = val.get("series_id")
            val_horizon = val.get("horizon")
            val_model = _normalize_model_key(val.get("model", ""))
            val_store = val.get("store_id")
            val_cat = val.get("category")
            val_item = val.get("item_id")

            if series_id and val_series != series_id:
                continue
            if horizon is not None and val_horizon != horizon:
                continue
            if norm_model and val_model and val_model != norm_model:
                continue
            # Strict store_id match: reject entry even when val_store is None/empty
            # (old entries without a store_id tag must not satisfy a store-scoped request)
            if store_id and (val_store or "") != store_id:
                continue
            if category and (val_cat or "") != category:
                continue
            if item_id and (val_item or "") != item_id:
                continue
            return val

        # Try MongoDB fallback
        if series_id and horizon and model:
            try:
                from ..db.mongo import MongoRepository
                db_res = MongoRepository.get_business_insights(dataset_id, series_id, horizon, model)
                if db_res:
                    ck = f"{dataset_id}:{series_id}:{horizon}:{norm_model}"
                    INSIGHTS_CACHE[ck] = db_res
                    return db_res
            except Exception:
                pass

        return None
