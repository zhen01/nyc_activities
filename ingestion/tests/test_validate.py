"""Tests for required-column and required-value validation."""

import pandas as pd
import pytest

from ingestion.validate import (
    IngestionValidationError,
    validate_required_columns,
    validate_required_values,
)


def test_validate_required_columns_passes_when_all_present() -> None:
    df = pd.DataFrame({"a": [1], "b": [2]})
    validate_required_columns(df, ["a", "b"], "test.csv")  # should not raise


def test_validate_required_columns_raises_when_missing() -> None:
    df = pd.DataFrame({"a": [1]})
    with pytest.raises(IngestionValidationError, match="b"):
        validate_required_columns(df, ["a", "b"], "test.csv")


def test_validate_required_values_raises_when_null() -> None:
    df = pd.DataFrame({"id": [1, 2], "name": ["x", None]})
    with pytest.raises(IngestionValidationError, match="name"):
        validate_required_values(df, ["name"], "id", "test.csv")


def test_validate_required_values_passes_when_populated() -> None:
    df = pd.DataFrame({"id": [1, 2], "name": ["x", "y"]})
    validate_required_values(df, ["name"], "id", "test.csv")  # should not raise
