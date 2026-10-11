import json
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd

from app.core.config import settings
from app.core.exceptions import DatasetNotFoundError
from app.services.dataset_service import DatasetService
from app.pipeline.splitter import ChronologicalSplitter
from app.models.model_factory import ModelFactory
from app.evaluation.engine import EvaluationEngine, ModelEvaluationResult
from app.evaluation.leaderboard import LeaderboardGenerator
from app.schemas.benchmark_schemas import (
    BenchmarkRunRequest,
    BenchmarkResultsResponse,
    ModelLeaderboardItem
)

class BenchmarkService:
    """Orchestrates multi-model historical backtesting and leaderboard ranking."""

    @staticmethod
    def run_benchmark(request: BenchmarkRunRequest) -> BenchmarkResultsResponse:
        # 1. Load canonical dataset
        df_canonical = DatasetService.get_canonical_dataframe(request.dataset_id)

        # 2. Chronological Train/Test Split (Strict temporal holdout)
        train_df, test_df, split_metadata = ChronologicalSplitter.split(
            df_canonical=df_canonical,
            train_percentage=request.train_percentage,
            fixed_test_days=request.fixed_test_days,
            series_id=request.series_id
        )

        evaluation_results: List[ModelEvaluationResult] = []
        model_predictions: Dict[str, List[float]] = {}

        # 3. Iterate through candidate models uniformly through BaseForecaster interface
        for model_key in request.candidate_models:
            try:
                model = ModelFactory.get_model(model_key)
                
                # Evaluate model strictly on train_df / test_df
                result = EvaluationEngine.evaluate_model(
                    model=model,
                    model_key=model_key,
                    train_df=train_df,
                    test_df=test_df
                )
                evaluation_results.append(result)
                model_predictions[result.model_name] = result.predictions
            except Exception as model_err:
                import traceback
                print(f"[Benchmark Warning] Model {model_key} failed evaluation: {model_err}")
                traceback.print_exc()

        if not evaluation_results:
            raise PreprocessingError("All candidate models failed during evaluation benchmark.")

        # 4. Generate dynamic leaderboard (Ranked by MAPE ascending, RMSE tie-breaker)
        raw_leaderboard = LeaderboardGenerator.generate_leaderboard(evaluation_results)
        leaderboard_items = [ModelLeaderboardItem(**item) for item in raw_leaderboard]

        # 5. Build multi-model comparison table for frontend charts
        test_timestamps = [str(ts.date()) for ts in pd.to_datetime(test_df["timestamp"])]
        actual_values = [round(float(a), 3) for a in test_df["target"].values]

        aligned_table = []
        for i, t_stamp in enumerate(test_timestamps):
            row = {
                "timestamp": t_stamp,
                "actual": actual_values[i]
            }
            for res in evaluation_results:
                row[res.model_name] = res.predictions[i]
            aligned_table.append(row)

        response = BenchmarkResultsResponse(
            dataset_id=request.dataset_id,
            split_info=split_metadata,
            leaderboard=leaderboard_items,
            test_timestamps=test_timestamps,
            test_actuals=actual_values,
            model_predictions=model_predictions,
            aligned_comparison_table=aligned_table,
            ranking_rule="Primary: MAPE (ascending, lower is better), Secondary: RMSE (ascending, lower is better)",
            message=f"Successfully evaluated {len(evaluation_results)} models across {len(test_df)} hidden test steps."
        )

        # 6. Cache results JSON to storage
        cache_file = settings.RESULTS_DIR / f"{request.dataset_id}_benchmark.json"
        with open(cache_file, "w") as f:
            json.dump(response.model_dump(), f, indent=2)

        return response

    @staticmethod
    def get_cached_results(dataset_id: str) -> BenchmarkResultsResponse:
        cache_file = settings.RESULTS_DIR / f"{dataset_id}_benchmark.json"
        if not cache_file.exists():
            raise DatasetNotFoundError(f"Benchmark results for dataset '{dataset_id}' not found. Please run benchmark first.")
        with open(cache_file, "r") as f:
            data = json.load(f)
        return BenchmarkResultsResponse(**data)
