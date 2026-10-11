import json
from datetime import datetime
from typing import List, Optional
import pandas as pd
import numpy as np

from app.core.config import settings
from app.core.exceptions import DatasetNotFoundError, PreprocessingError
from app.services.dataset_service import DatasetService
from app.models.model_factory import ModelFactory
from app.insights.insights_engine import InsightsEngine
from app.schemas.forecast_schemas import (
    ForecastRunRequest,
    ForecastDataPoint,
    ForecastResultsResponse
)

class ForecastService:
    """
    Coordinates 100% historical retraining, future horizon inference,
    uncertainty bounds alignment, and business insights computation.
    """

    @staticmethod
    def generate_future_forecast(request: ForecastRunRequest) -> ForecastResultsResponse:
        # 1. Load canonical dataset
        df_canonical = DatasetService.get_canonical_dataframe(request.dataset_id)
        df = df_canonical.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        # 2. Filter by series_id if requested, otherwise aggregate
        series_label = "all_series"
        if request.series_id:
            df["_series_str"] = df["series_id"].astype(str)
            target_str = str(request.series_id)
            filtered = df[df["_series_str"] == target_str].copy()
            if filtered.empty:
                available = df["series_id"].dropna().unique()
                if len(available) > 0:
                    filtered = df[df["series_id"] == available[0]].copy()
                    series_label = str(available[0])
            else:
                series_label = str(request.series_id)
            if filtered.empty:
                raise PreprocessingError(f"Series ID '{request.series_id}' not found in dataset '{request.dataset_id}'.")
            df = filtered.drop(columns=["_series_str"], errors="ignore")

        # Sort strictly by timestamp
        df_full = df.sort_values("timestamp").reset_index(drop=True)
        if len(df_full) < 5:
            raise PreprocessingError(f"Dataset has only {len(df_full)} observations. At least 5 are required.")

        historical_start = str(df_full["timestamp"].min().date())
        historical_end = str(df_full["timestamp"].max().date())
        hist_count = len(df_full)

        # 3. Instantiate model
        model = ModelFactory.get_model(request.model)

        # 4. Retrain STRICTLY on 100% of historical data (Zero artificial holdout)
        model.fit(df_full)

        # 5. Predict future horizon
        output = model.predict(horizon_steps=request.horizon)

        # 6. Build and validate forecast points with non-negativity and monotonic bounds
        forecast_points: List[ForecastDataPoint] = []
        for i in range(request.horizon):
            t_str = output.timestamps[i]
            pred = max(0.0, float(output.predictions[i]))

            # Extract bounds with non-negativity & monotonic ordering
            raw_l80 = float(output.lower_bound_80[i]) if output.lower_bound_80 and len(output.lower_bound_80) > i else pred * 0.90
            raw_u80 = float(output.upper_bound_80[i]) if output.upper_bound_80 and len(output.upper_bound_80) > i else pred * 1.10
            raw_l95 = float(output.lower_bound_95[i]) if output.lower_bound_95 and len(output.lower_bound_95) > i else pred * 0.85
            raw_u95 = float(output.upper_bound_95[i]) if output.upper_bound_95 and len(output.upper_bound_95) > i else pred * 1.15

            # Enforce: 0 <= l95 <= l80 <= pred <= u80 <= u95
            l95 = max(0.0, min(pred, raw_l95))
            l80 = max(l95, min(pred, raw_l80))
            u80 = max(pred, raw_u80)
            u95 = max(u80, raw_u95)

            forecast_points.append(ForecastDataPoint(
                timestamp=t_str,
                prediction=round(pred, 3),
                lower_80=round(l80, 3),
                upper_80=round(u80, 3),
                lower_95=round(l95, 3),
                upper_95=round(u95, 3)
            ))

        # 7. Compute Business Insights
        insights = InsightsEngine.calculate_insights(
            forecast_points=forecast_points,
            current_inventory=request.current_inventory
        )

        forecast_start = forecast_points[0].timestamp
        forecast_end = forecast_points[-1].timestamp
        forecast_id = f"fc_{request.dataset_id}_{request.model}_{request.horizon}d"

        response = ForecastResultsResponse(
            forecast_id=forecast_id,
            dataset_id=request.dataset_id,
            series_id=series_label,
            selected_model=model.name,
            model_type=model.model_type,
            retrained_on_full_history=True,
            historical_observations_count=hist_count,
            historical_start=historical_start,
            historical_end=historical_end,
            forecast_start=forecast_start,
            forecast_end=forecast_end,
            horizon=request.horizon,
            forecast=forecast_points,
            insights=insights,
            created_at=datetime.utcnow().isoformat() + "Z",
            message=f"Successfully generated {request.horizon}-day future forecast using {model.name} retrained on 100% historical data."
        )

        # 8. Cache results
        cache_path = settings.RESULTS_DIR / f"{forecast_id}.json"
        with open(cache_path, "w") as f:
            json.dump(response.model_dump(), f, indent=2)

        return response

    @staticmethod
    def get_cached_forecast(forecast_id: str) -> ForecastResultsResponse:
        cache_path = settings.RESULTS_DIR / f"{forecast_id}.json"
        if not cache_path.exists():
            raise DatasetNotFoundError(f"Forecast with ID '{forecast_id}' not found. Please run forecast first.")
        with open(cache_path, "r") as f:
            data = json.load(f)
        return ForecastResultsResponse(**data)
