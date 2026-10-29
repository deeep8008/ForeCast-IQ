"""
Horizon Management and Validation (Phase 7)
ForecastIQ Backend

Validates and manages multi-horizon parameters (7D, 28D, 90D).
Ensures history requirements and cutoff bounds are checked consistently.
"""
from typing import List, Dict, Any, Optional
from ..models.config import ModelDefaults


class HorizonManager:
    """
    Manages multi-horizon definitions, feasibility checks, and temporal requirements.
    Supported horizons: 7, 28, 90 days.
    """
    SUPPORTED_HORIZONS: List[int] = [7, 28, 90]

    HORIZON_METADATA: Dict[int, Dict[str, Any]] = {
        7: {
            "name": "7 Days",
            "term": "Short-term",
            "business_focus": "Daily operational inventory & replenishment",
            "min_history_required": 14,
        },
        28: {
            "name": "28 Days",
            "term": "Medium-term",
            "business_focus": "Store staffing, shift planning & monthly allocation",
            "min_history_required": 35,
        },
        90: {
            "name": "90 Days",
            "term": "Long-term",
            "business_focus": "Strategic supplier contracts, capacity & lead times",
            "min_history_required": 100,
        },
    }

    @classmethod
    def validate_horizon(cls, horizon: int) -> int:
        """
        Validate that the requested horizon is an allowed multi-horizon tier.
        Raises ValueError with clear message if unsupported.
        """
        if horizon not in cls.SUPPORTED_HORIZONS:
            allowed = ", ".join(f"{h}D" for h in cls.SUPPORTED_HORIZONS)
            raise ValueError(
                f"Invalid forecast horizon: {horizon} days. "
                f"Supported multi-horizon options are: {allowed}."
            )
        return horizon

    @classmethod
    def validate_history_sufficiency(cls, horizon: int, observation_count: int, model_name: str = "Forecasting model") -> None:
        """
        Validate that the historical observation count satisfies the minimum threshold
        for the given horizon and model architecture.
        """
        meta = cls.HORIZON_METADATA.get(horizon)
        min_required = meta["min_history_required"] if meta else horizon * 2
        
        # Deep learning models require slightly higher history for training chunks
        if model_name.lower() in ["deepar", "tft"]:
            min_required = max(min_required, 40 if horizon == 7 else (60 if horizon == 28 else 100))

        if observation_count < min_required:
            raise ValueError(
                "Not enough historical data for this forecast horizon. "
                f"Available: {observation_count} observations. Required: {min_required} observations. "
                f"[{model_name} @ {horizon}D]"
            )

    @classmethod
    def get_metadata(cls, horizon: int) -> Dict[str, Any]:
        """Return business and technical metadata for horizon."""
        return cls.HORIZON_METADATA.get(horizon, {
            "name": f"{horizon} Days",
            "term": "Custom",
            "business_focus": "Custom horizon forecasting",
            "min_history_required": horizon * 2
        })
