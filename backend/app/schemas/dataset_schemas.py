from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class DatasetUploadResponse(BaseModel):
    dataset_id: str
    dataset_name: str
    detected_type: str = Field(description="'single_csv', 'multi_csv_folder', or 'm5_dataset'")
    csv_files: List[str]
    available_columns: List[str]
    preview_rows: List[Dict[str, Any]]
    total_raw_rows: int
    message: str

class ColumnMappingRequest(BaseModel):
    dataset_id: str
    time_column: str
    target_column: str
    series_id_column: Optional[str] = None
    secondary_series_id_column: Optional[str] = None
    dynamic_covariates: List[str] = Field(default_factory=list)
    static_covariates: List[str] = Field(default_factory=list)
    selected_file: Optional[str] = None

class ColumnMappingResponse(BaseModel):
    dataset_id: str
    canonical_rows_count: int
    series_count: int
    start_date: str
    end_date: str
    detected_frequency: str
    status: str
    message: str

class DatasetSummaryResponse(BaseModel):
    dataset_id: str
    dataset_name: str
    total_observations: int
    series_count: int
    series_ids: List[str]
    start_date: str
    end_date: str
    frequency: str
    missing_values_found: int
    missing_values_imputed: int
    target_stats: Dict[str, float]
    sample_records: List[Dict[str, Any]]

class M5PreloadRequest(BaseModel):
    aggregation_level: str = Field(default="total", description="'total', 'store', 'state', or 'dept'")
    max_days: Optional[int] = Field(default=None, description="Optional cap on days for fast ingestion (e.g. 500)")
    max_series: Optional[int] = Field(default=10, description="Max individual series to load if aggregating by store/dept")
