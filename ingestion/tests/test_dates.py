"""Tests for malformed date handling."""

import pandas as pd
import pytest

from ingestion.validate import IngestionValidationError, parse_date_columns


def test_parse_date_columns_parses_valid_dates() -> None:
    df = pd.DataFrame({"id": [1, 2], "start_time": ["2026-07-01", "2026-07-02"]})
    result = parse_date_columns(df, ["start_time"], "id", "test.csv")
    assert pd.api.types.is_datetime64_any_dtype(result["start_time"])


def test_parse_date_columns_raises_on_malformed_date() -> None:
    df = pd.DataFrame({"id": [1, 2], "start_time": ["2026-07-01", "not-a-date"]})
    with pytest.raises(IngestionValidationError, match="start_time"):
        parse_date_columns(df, ["start_time"], "id", "test.csv")


def test_parse_date_columns_allows_missing_optional_date() -> None:
    df = pd.DataFrame({"id": [1, 2], "last_checked": ["2026-07-01", None]})
    result = parse_date_columns(df, ["last_checked"], "id", "test.csv")
    assert pd.isna(result.loc[1, "last_checked"])
