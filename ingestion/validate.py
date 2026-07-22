"""Validation helpers for ingestion CSVs: required columns, required
values, and date parsing. Each check raises IngestionValidationError with
a message that names the file, column, and offending row(s), so failures
are diagnosable without reading a stack trace.
"""

from __future__ import annotations

import pandas as pd


class IngestionValidationError(Exception):
    """Raised when input CSV data fails a validation check."""


def validate_required_columns(df: pd.DataFrame, required: list[str], file_label: str) -> None:
    """Raise if any column in `required` is missing from df's header."""
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise IngestionValidationError(
            f"{file_label}: missing required column(s): {', '.join(missing)}"
        )


def validate_required_values(
    df: pd.DataFrame, required: list[str], id_column: str, file_label: str
) -> None:
    """Raise if any required column has a null/empty value in any row."""
    for col in required:
        bad_rows = df[df[col].isna()]
        if not bad_rows.empty:
            ids = (
                bad_rows[id_column].tolist()
                if id_column in df.columns
                else bad_rows.index.tolist()
            )
            raise IngestionValidationError(
                f"{file_label}: required column '{col}' is missing a value for row(s): {ids}"
            )


def parse_date_columns(
    df: pd.DataFrame, date_columns: list[str], id_column: str, file_label: str
) -> pd.DataFrame:
    """Parse each column in `date_columns` to datetime, raising clearly on
    malformed (non-empty, unparseable) values. Empty/missing values are
    left as null (they're optional unless also listed as a required column).
    """
    df = df.copy()
    for col in date_columns:
        if col not in df.columns:
            continue
        original = df[col]
        parsed = pd.to_datetime(original, errors="coerce")
        non_empty = original.notna() & (original.astype(str).str.strip() != "")
        bad_mask = parsed.isna() & non_empty
        if bad_mask.any():
            bad_ids = (
                df.loc[bad_mask, id_column].tolist()
                if id_column in df.columns
                else df.index[bad_mask].tolist()
            )
            bad_values = original[bad_mask].tolist()
            raise IngestionValidationError(
                f"{file_label}: column '{col}' has malformed date value(s) "
                f"{bad_values} in row(s) {bad_ids}"
            )
        df[col] = parsed
    return df
