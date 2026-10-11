from pathlib import Path
from typing import List, Dict, Any, Tuple
import pandas as pd
from app.data_adapters.base_adapter import BaseDatasetAdapter
from app.pipeline.validator import DatasetValidator
from app.schemas.dataset_schemas import ColumnMappingRequest
from app.core.exceptions import InvalidSchemaError

class GenericCSVAdapter(BaseDatasetAdapter):
    """Universal adapter for any standard single-CSV or multi-CSV time-series dataset."""

    def validate_source(self, raw_path: Path) -> List[Path]:
        return DatasetValidator.scan_directory_for_csvs(raw_path)

    def extract_preview(self, raw_path: Path, n_rows: int = 5, selected_file: str = None) -> Tuple[List[str], List[Dict[str, Any]], int]:
        csv_files = self.validate_source(raw_path)
        
        target_csv = csv_files[0]
        if selected_file:
            for f in csv_files:
                if f.name == selected_file:
                    target_csv = f
                    break

        df_preview = pd.read_csv(target_csv, nrows=n_rows)
        # Get quick line count (or estimate)
        try:
            with open(target_csv, "r", encoding="utf-8", errors="ignore") as f:
                total_lines = sum(1 for _ in f) - 1
        except Exception:
            total_lines = len(df_preview)

        columns = list(df_preview.columns)
        # Clean preview rows for JSON serialization
        preview_rows = df_preview.fillna("").to_dict(orient="records")
        return columns, preview_rows, max(0, total_lines)

    def transform_to_canonical(self, raw_path: Path, mapping: ColumnMappingRequest) -> pd.DataFrame:
        csv_files = self.validate_source(raw_path)
        target_csv = csv_files[0]
        if mapping.selected_file:
            for f in csv_files:
                if f.name == mapping.selected_file:
                    target_csv = f
                    break

        df_raw = pd.read_csv(target_csv)
        DatasetValidator.validate_columns_exist(
            df_raw,
            time_col=mapping.time_column,
            target_col=mapping.target_column,
            series_id_col=mapping.series_id_column,
            secondary_series_id_col=mapping.secondary_series_id_column
        )

        # Parse time and target
        parsed_time = DatasetValidator.validate_and_parse_timestamps(df_raw, mapping.time_column)
        parsed_target = DatasetValidator.validate_numeric_target(df_raw, mapping.target_column)

        # Build canonical columns
        canonical_df = pd.DataFrame()
        canonical_df["timestamp"] = parsed_time
        canonical_df["target"] = parsed_target

        if mapping.secondary_series_id_column and mapping.series_id_column:
            # e.g. "Store 1 - Item 1" or "Dallas / SKU123"
            canonical_df["series_id"] = (
                df_raw[mapping.secondary_series_id_column].astype(str)
                + " / "
                + df_raw[mapping.series_id_column].astype(str)
            )
        elif mapping.series_id_column:
            canonical_df["series_id"] = df_raw[mapping.series_id_column].astype(str)
        elif mapping.secondary_series_id_column:
            canonical_df["series_id"] = df_raw[mapping.secondary_series_id_column].astype(str)
        else:
            canonical_df["series_id"] = "total"

        # Add covariates if requested
        for cov in mapping.dynamic_covariates:
            if cov in df_raw.columns:
                canonical_df[cov] = df_raw[cov]

        for cov in mapping.static_covariates:
            if cov in df_raw.columns:
                canonical_df[cov] = df_raw[cov]

        # Drop any records with unparseable timestamps or targets
        canonical_df = canonical_df.dropna(subset=["timestamp", "target"])
        return canonical_df
