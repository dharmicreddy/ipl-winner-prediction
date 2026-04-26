"""Smoke tests for the modeling data loader.

These confirm the warehouse → numpy bridge works correctly with the actual
data we expect (218 matches across 3 splits).
"""

from __future__ import annotations

import psycopg
import pytest

from ingestion.db.connection import get_connection
from models.data import (
    CATEGORICAL_FEATURES,
    LABEL,
    NUMERIC_FEATURES,
    build_splits,
    load_match_set,
)


def _postgres_available() -> bool:
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    except (psycopg.Error, RuntimeError, OSError):
        return False


pytestmark = pytest.mark.skipif(
    not _postgres_available(),
    reason="Postgres not reachable — skip integration test",
)


def test_load_match_set_returns_expected_shape():
    df = load_match_set()
    assert len(df) == 218, f"expected 218 matches, got {len(df)}"
    expected_cols = set(NUMERIC_FEATURES + CATEGORICAL_FEATURES + [LABEL, "split"])
    assert expected_cols.issubset(set(df.columns))


def test_build_splits_preserves_total_count():
    train, val, holdout, _enc = build_splits()
    assert train.X.shape[0] + val.X.shape[0] + holdout.X.shape[0] == 218


def test_build_splits_train_size():
    train, _val, _holdout, _enc = build_splits()
    assert train.X.shape[0] == 74


def test_build_splits_features_consistent():
    train, val, holdout, _enc = build_splits()
    # Same number of feature columns across all splits
    assert train.X.shape[1] == val.X.shape[1] == holdout.X.shape[1]
    # Feature names are the same list
    assert train.feature_names == val.feature_names == holdout.feature_names
