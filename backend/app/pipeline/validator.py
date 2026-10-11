from pathlib import Path
from typing import List, Tuple
import pandas as pd
from app.core.exceptions import NoCsvFoundError, InvalidSchemaError

class DatasetValidator:
    """Validates files, directories, and dataframes for time-series compatibility."""

    @staticmethod
    def scan_directory_for_csvs(directory_path: Path) -> List[Path]:
        """
        Scans a directory recursively to find all .csv files.
        Raises NoCsvFoundError if no .csv files exist.
        """
        if not directory_path.exists():
            raise NoCsvFoundError(f"Upload directory '{directory_path}' does not exist.")
            
        csv_files = list(directory_path.glob("*.csv")) + list(directory_path.glob("*/*.csv"))
        # De-duplicate while preserving order
        unique_csvs = []
        seen = set()
        for f in csv_files:
            if f.resolve() not in seen:
                unique_csvs.append(f)
                seen.add(f.resolve())

        if not unique_csvs:
            raise NoCsvFoundError(
                "No valid .csv files were detected in the uploaded selection. "
                "Please upload a file or folder containing at least one .csv file."
            )
        return unique_csvs

    @staticmethod
    def validate_columns_exist(
        df: pd.DataFrame, 
        time_col: str, 
        target_col: str, 
        series_id_col: str = None,
        secondary_series_id_col: str = None
    ) -> None:
        """Verifies that user-mapped columns actually exist in the dataframe."""
        missing = []
        if time_col not in df.columns:
            missing.append(f"Timestamp column '{time_col}'")
        if target_col not in df.columns:
            missing.append(f"Target column '{target_col}'")
        if series_id_col and series_id_col not in df.columns:
            missing.append(f"Series ID column '{series_id_col}'")
        if secondary_series_id_col and secondary_series_id_col not in df.columns:
            missing.append(f"Location / Group column '{secondary_series_id_col}'")

        if missing:
            raise InvalidSchemaError(f"Missing mapped columns in dataset: {', '.join(missing)}")

    @staticmethod
    def validate_and_parse_timestamps(df: pd.DataFrame, time_col: str) -> pd.Series:
        """Attempts to parse timestamp column into datetime. Raises InvalidSchemaError on complete failure."""
        try:
            parsed = pd.to_datetime(df[time_col], errors="coerce")
            null_count = parsed.isna().sum()
            if null_count == len(df):
                raise InvalidSchemaError(
                    f"Column '{time_col}' could not be parsed as valid dates or timestamps."
                )
            if null_count > 0.3 * len(df):
                raise InvalidSchemaError(
                    f"Column '{time_col}' contains over 30% invalid date values ({null_count} errors)."
                )
            return parsed
        except Exception as e:
            raise InvalidSchemaError(f"Error parsing date column '{time_col}': {str(e)}")

    @staticmethod
    def validate_numeric_target(df: pd.DataFrame, target_col: str) -> pd.Series:
        """Validates that target column can be converted to float."""
        try:
            target_series = pd.to_numeric(df[target_col], errors="coerce")
            null_count = target_series.isna().sum()
            if null_count == len(df):
                raise InvalidSchemaError(
                    f"Target column '{target_col}' contains no numeric values."
                )
            return target_series
        except Exception as e:
            raise InvalidSchemaError(f"Target column '{target_col}' must be numeric: {str(e)}")
