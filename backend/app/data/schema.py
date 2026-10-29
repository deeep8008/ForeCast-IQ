"""
Canonical Schema Definition for Universal Time-Series Datasets
ForecastIQ — Multi-Horizon Time-Series Forecasting for Enterprise Analytics
"""
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class CanonicalField(str, Enum):
    # Mandatory
    DATE = "date"
    SERIES_ID = "series_id"
    TARGET = "target"
    
    # Optional standard covariates
    STORE_ID = "store_id"
    ITEM_ID = "item_id"
    CATEGORY = "category"
    COMPANY = "company"
    REGION = "region"
    STATE = "state"
    PRICE = "price"
    PROMOTION = "promotion"
    HOLIDAY = "holiday"
    WEATHER = "weather"
    CUSTOMER_SEGMENT = "customer_segment"


MANDATORY_CANONICAL_FIELDS = [
    CanonicalField.DATE.value,
    CanonicalField.TARGET.value,
]

OPTIONAL_CANONICAL_FIELDS = [
    CanonicalField.SERIES_ID.value,
    CanonicalField.STORE_ID.value,
    CanonicalField.ITEM_ID.value,
    CanonicalField.CATEGORY.value,
    CanonicalField.COMPANY.value,
    CanonicalField.REGION.value,
    CanonicalField.STATE.value,
    CanonicalField.PRICE.value,
    CanonicalField.PROMOTION.value,
    CanonicalField.HOLIDAY.value,
    CanonicalField.WEATHER.value,
    CanonicalField.CUSTOMER_SEGMENT.value,
]


class ColumnClassification(str, Enum):
    TIME = "TIME"
    TARGET = "TARGET"
    SERIES_ID = "SERIES_ID"
    NUMERICAL = "NUMERICAL"
    CATEGORICAL = "CATEGORICAL"
    IDENTIFIER = "IDENTIFIER"
    POTENTIALLY_USEFUL = "POTENTIALLY_USEFUL"
    CONSTANT = "CONSTANT"
    POTENTIAL_LEAKAGE = "POTENTIAL_LEAKAGE"
    KNOWN_FUTURE = "KNOWN_FUTURE"
    HISTORICAL_ONLY = "HISTORICAL_ONLY"
    FUTURE_PROVIDED = "FUTURE_PROVIDED"


class ReadinessStatus(str, Enum):
    READY = "READY"
    NEEDS_ATTENTION = "NEEDS_ATTENTION"
    INVALID = "INVALID"


class ColumnFeatureProfile(BaseModel):
    name: str
    data_type: str
    unique_count: int
    missing_count: int
    missing_percentage: float
    classification: ColumnClassification
    reason: str
    sample_values: List[Any] = Field(default_factory=list)


class ColumnMapping(BaseModel):
    date: str
    series_id: Optional[str] = None
    target: str
    composite_series_keys: Optional[List[str]] = Field(default_factory=list)
    candidate_entity_columns: Optional[List[str]] = Field(default_factory=list)
    optional: Dict[str, str] = Field(default_factory=dict)


class TargetStatistics(BaseModel):
    count: int
    mean: Optional[float] = None
    std: Optional[float] = None
    min: Optional[float] = None
    q25: Optional[float] = None
    median: Optional[float] = None
    q75: Optional[float] = None
    max: Optional[float] = None
    zero_count: int = 0
    negative_count: int = 0


class DateRangeProfile(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    total_days: int = 0


class DatasetProfile(BaseModel):
    dataset_id: str
    filename: str
    rows_count: int
    columns_count: int
    column_names: List[str]
    detected_frequency: str
    unique_series_count: int
    date_range: DateRangeProfile
    target_statistics: TargetStatistics
    missing_values_total: int
    missing_values_pct: float
    duplicate_rows_count: int
    conflicting_records_count: int
    numerical_columns: List[str]
    categorical_columns: List[str]
    identifier_columns: List[str]


class SeriesQualityItem(BaseModel):
    series_id: str
    observation_count: int
    start_date: str
    end_date: str
    span_days: int
    missing_dates_count: int
    duplicate_dates_count: int
    is_regular: bool


class SeriesSummary(BaseModel):
    total_series: int
    series_with_gaps: int
    min_observations: int
    median_observations: int
    max_observations: int
    sample_series_quality: List[SeriesQualityItem] = Field(default_factory=list)


class ValidationReport(BaseModel):
    dataset_id: str
    status: ReadinessStatus
    errors: List[str]
    warnings: List[str]
    missing_mandatory_fields: List[str]
    mapped_fields: ColumnMapping
    exact_duplicate_rows: int
    conflicting_series_date_records: int
    invalid_dates_count: int
    invalid_target_values_count: int
    negative_target_values_count: int


class HorizonReadiness(BaseModel):
    days: int
    label: str
    status: str  # Supported, Borderline, Insufficient
    note: str


class ModelReadiness(BaseModel):
    model: str
    type: str
    ready: bool
    requirement: str


class ReadinessReport(BaseModel):
    dataset_id: str
    filename: str
    status: ReadinessStatus
    errors: List[str]
    warnings: List[str]
    profile: DatasetProfile
    column_mapping: ColumnMapping
    feature_classifications: List[ColumnFeatureProfile]
    series_summary: SeriesSummary
    readiness_checklist: List[Dict[str, Any]]
    supported_horizons: Dict[str, HorizonReadiness]
    model_compatibility: List[ModelReadiness]


class PipelineStatus(str, Enum):
    ANALYZING = "ANALYZING"
    CLEANING = "CLEANING"
    NEEDS_ATTENTION = "NEEDS_ATTENTION"
    READY_FOR_MODEL_TRAINING = "READY FOR MODEL TRAINING"


class ConflictResolutionReport(BaseModel):
    conflicts_found: int = 0
    identical_duplicates_resolved: int = 0
    additive_conflicts_resolved: int = 0
    unresolved_conflicts: int = 0
    aggregation_applied: str = "SUM"
    details: List[str] = Field(default_factory=list)


class CleaningReport(BaseModel):
    dataset_id: str
    original_rows: int
    cleaned_rows: int
    exact_duplicates_removed: int
    conflicts_detected: int
    conflicts_resolved: int
    unresolved_conflicts: int
    aggregation_rule: str
    missing_targets_found: int
    missing_targets_handled: str
    zero_targets_preserved: int
    negative_targets_flagged: int
    negative_series_affected: List[str] = Field(default_factory=list)
    optional_imputations_count: int
    gaps_detected_count: int
    outliers_contextual_count: int
    outliers_abnormal_count: int
    pipeline_status: PipelineStatus
    summary_notes: List[str] = Field(default_factory=list)
    # Explicitly defined reconciliation fields
    raw_row_count: int = 0
    exact_duplicate_rows_removed: int = 0
    invalid_date_rows_excluded: int = 0
    conflicting_observation_groups_resolved: int = 0
    missing_target_rows_excluded_or_imputed: int = 0
    cleaned_row_count: int = 0
    eligible_for_training_row_count: int = 0


class SeriesQualityMetrics(BaseModel):
    series_id: str
    observation_count: int
    start_date: str
    end_date: str
    span_days: int
    frequency: str
    missing_target_count: int
    duplicate_count: int
    conflict_count: int
    gap_count: int
    zero_count: int
    negative_count: int
    outlier_count: int
    target_mean: Optional[float] = None
    target_std: Optional[float] = None
    target_min: Optional[float] = None
    target_median: Optional[float] = None
    target_max: Optional[float] = None
    horizon_7d_feasible: bool = False
    horizon_28d_feasible: bool = False
    horizon_90d_feasible: bool = False
    status: str = "READY"
    note: str = ""


class SeriesQualityAnalysisReport(BaseModel):
    dataset_id: str
    total_series: int
    feasible_7d_count: int
    feasible_28d_count: int
    feasible_90d_count: int
    all_series_metrics: List[SeriesQualityMetrics] = Field(default_factory=list)


class SplitSet(BaseModel):
    name: str
    start_date: str
    end_date: str
    rows_count: int
    series_count: int


class SplitReport(BaseModel):
    dataset_id: str
    train: SplitSet
    val: SplitSet
    test: SplitSet
    split_strategy: str
    test_horizon_days: int
    val_horizon_days: int
    train_row_count: int = 0
    validation_row_count: int = 0
    test_row_count: int = 0
    split_ratio: str = "80:20"
    train_pct: float = 80.0
    test_pct: float = 20.0


class CleanDatasetRequest(BaseModel):
    additive_aggregation: bool = True  # If True, SUM additive targets for identical series+date
    target_type: Optional[str] = "additive"  # 'additive' or 'non-additive'
    impute_optional_features: bool = True
    series_id: Optional[str] = None
    composite_series_keys: Optional[List[str]] = None


class UploadResponse(BaseModel):
    dataset_id: str
    filename: str
    rows: int
    columns: int
    status: ReadinessStatus
    detected_mapping: ColumnMapping
    summary: str


# Phase 4: Statistical Forecasting Models & Predictions
class ForecastPoint(BaseModel):
    date: str
    forecast: float
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None


class ForecastResult(BaseModel):
    dataset_id: str
    series_id: str
    model: str
    forecast_horizon: int
    dates: List[str]
    forecast: List[float]
    lower_bound: Optional[List[float]] = None
    upper_bound: Optional[List[float]] = None
    points: List[ForecastPoint] = Field(default_factory=list)
    components: Optional[Dict[str, Any]] = None
    training_start: Optional[str] = None
    training_end: Optional[str] = None
    forecast_start: Optional[str] = None
    forecast_end: Optional[str] = None
    execution_time_ms: float = 0.0
    status: str = "SUCCESS"
    notes: List[str] = Field(default_factory=list)
    store_id: Optional[str] = None
    category: Optional[str] = None
    item_id: Optional[str] = None
    scope: Optional[Dict[str, Any]] = None
    history: Optional[List[Dict[str, Any]]] = None


class ArimaConfig(BaseModel):
    p: int = 1
    d: int = 1
    q: int = 1


class SarimaConfig(BaseModel):
    p: int = 1
    d: int = 1
    q: int = 1
    P: int = 1
    D: int = 0
    Q: int = 1
    seasonal_period: int = 7


class ProphetConfig(BaseModel):
    yearly_seasonality: bool = False
    weekly_seasonality: bool = True
    daily_seasonality: bool = False
    interval_width: float = 0.95


class LightgbmConfig(BaseModel):
    n_estimators: int = 100
    learning_rate: float = 0.05
    num_leaves: int = 31
    max_depth: int = -1
    subsample: float = 0.8
    random_state: int = 42


class DeeparConfig(BaseModel):
    input_chunk_length: int = 14
    training_length: int = 28
    epochs: int = 15
    batch_size: int = 16
    hidden_dim: int = 20
    num_layers: int = 2
    dropout: float = 0.1
    random_state: int = 42
    num_samples: int = 100


class TftConfig(BaseModel):
    input_chunk_length: int = 14
    output_chunk_length: int = 7
    epochs: int = 15
    batch_size: int = 16
    hidden_size: int = 16
    lstm_layers: int = 1
    num_attention_heads: int = 2
    dropout: float = 0.1
    random_state: int = 42


class ForecastRequest(BaseModel):
    dataset_id: str
    series_id: Optional[str] = None
    store_id: Optional[str] = None
    category: Optional[str] = None
    item_id: Optional[str] = None
    horizon: int = 28  # 7, 28, or 90
    model: str = "arima"  # arima, sarima, prophet, lightgbm, deepar, tft, automatic
    arima_config: Optional[ArimaConfig] = None
    sarima_config: Optional[SarimaConfig] = None
    prophet_config: Optional[ProphetConfig] = None
    lightgbm_config: Optional[LightgbmConfig] = None
    deepar_config: Optional[DeeparConfig] = None
    tft_config: Optional[TftConfig] = None


class BacktestRequest(BaseModel):
    dataset_id: str
    series_ids: Optional[List[str]] = None
    store_id: Optional[str] = None
    category: Optional[str] = None
    item_id: Optional[str] = None
    models: Optional[List[str]] = None
    horizons: Optional[List[int]] = None
    n_folds: int = 2


class BestModelHorizonInfo(BaseModel):
    best_model: str
    mape: Optional[float] = None
    rmse: Optional[float] = None
    is_tie: bool = False
    tied_models: List[str] = Field(default_factory=list)


class EvaluationSummaryResponse(BaseModel):
    dataset_id: str
    models_evaluated: List[str]
    horizons_evaluated: List[str]
    total_series_evaluated: int
    total_evaluations_count: int
    execution_duration_ms: float
    table_1_model_x_horizon_mape: Dict[str, Dict[str, Optional[float]]]
    table_2_model_x_horizon_rmse: Dict[str, Dict[str, Optional[float]]]
    table_3_series_evaluations: List[Dict[str, Any]]
    best_per_horizon: Dict[str, Optional[BestModelHorizonInfo]]
    best_model_overall: Optional[Dict[str, Any]] = None
    series_details: Optional[List[Dict[str, Any]]] = None
    scope: Optional[Dict[str, Any]] = None


class RecommendationItem(BaseModel):
    category: str
    recommendation: str
    priority: str
    reason: str
    evidence: Dict[str, Any]
    planning_period: str
    uncertainty: str
    horizon: int


class DemandOutlook(BaseModel):
    recent_average_demand: float
    forecast_average_demand: float
    expected_change_pct: float
    expected_peak: Dict[str, Any]
    expected_low: Dict[str, Any]
    forecast_period: str
    demand_direction: str
    variability: float
    uncertainty_level: str


class BusinessInsightsResponse(BaseModel):
    dataset_id: str
    series_id: str
    model: str
    horizon: int
    store_id: Optional[str] = None
    category: Optional[str] = None
    item_id: Optional[str] = None
    scope: Optional[Dict[str, Any]] = None
    demand_outlook: DemandOutlook
    inventory_recommendation: RecommendationItem
    staffing_recommendation: RecommendationItem
    procurement_recommendation: RecommendationItem
    demand_planning: Dict[str, Any]
    horizon_insights: Dict[str, str]
    optional_feature_context: Optional[Dict[str, Any]] = None


class InsightRequest(BaseModel):
    dataset_id: str
    series_id: Optional[str] = None
    store_id: Optional[str] = None
    category: Optional[str] = None
    item_id: Optional[str] = None
    model: str = "automatic"
    horizon: int = 28


class MonitoringReport(BaseModel):
    dataset_id: str
    status: str
    baseline_mape: Optional[float] = None
    recent_mape: Optional[float] = None
    mape_drift_pct: Optional[float] = None
    retraining_alert: Optional[str] = None
    is_alert: bool = False
    models_tracked: List[str] = Field(default_factory=list)
    details: Optional[List[Dict[str, Any]]] = None
    store_id: Optional[str] = None
    category: Optional[str] = None
    item_id: Optional[str] = None
    series_id: Optional[str] = None
    horizon: Optional[int] = None
    scope: Optional[Dict[str, Any]] = None

# ---------------------------------------------------------------------------
# Data Explorer Schemas (Full Dataset Analytics)
# ---------------------------------------------------------------------------
class ExplorerTrendPoint(BaseModel):
    date: str
    sales: float
    rollingAvg: float


class ExplorerBreakdownItem(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    val: Optional[float] = None
    pct: Optional[float] = None
    count: Optional[float] = None
    share: Optional[str] = None


class ExplorerDimensions(BaseModel):
    has_store: bool = False
    has_category: bool = False
    has_item: bool = False
    has_series: bool = True
    has_price: bool = False


class ExplorerAvailableFilters(BaseModel):
    stores: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)
    items: List[str] = Field(default_factory=list)
    series: List[str] = Field(default_factory=list)


class ExplorerScope(BaseModel):
    dataset_id: str
    store_id: Optional[str] = None
    category: Optional[str] = None
    item_id: Optional[str] = None
    series_id: Optional[str] = None
    date_range: Optional[str] = "all"


class ExplorerResponse(BaseModel):
    dataset_id: str
    scope: ExplorerScope
    dimensions: ExplorerDimensions
    available_filters: ExplorerAvailableFilters
    total_rows: int
    total_series: int
    total_demand: float
    avg_daily_demand: float
    max_demand: float
    min_demand: float
    zero_days_count: int
    zero_days_pct: float
    date_min: str
    date_max: str
    trend: List[ExplorerTrendPoint] = Field(default_factory=list)
    store_breakdown: List[ExplorerBreakdownItem] = Field(default_factory=list)
    category_breakdown: List[ExplorerBreakdownItem] = Field(default_factory=list)
    item_breakdown: List[ExplorerBreakdownItem] = Field(default_factory=list)
    price_movement: Optional[Dict[str, Any]] = None
