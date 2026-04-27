"""Build deployable dashboard assets: SQLite snapshot + pickled model.

Generates two files committed to the repo:
- dashboard/data/ipl.sqlite : a read-only SQLite copy of the gold + features tables
- dashboard/data/model.pkl  : the calibrated XGBoost classifier as a portable pickle

These files let the Streamlit Cloud deployment work without access to our
local Postgres or MLflow tracking server. The script is idempotent: running
it twice produces identical (modulo timestamps) outputs.

Usage:
    python -m scripts.build_dashboard_assets

Requires the local Postgres to be running and populated (run the pipeline
first if it isn't).
"""

from __future__ import annotations

import logging
import pickle
import sqlite3
from pathlib import Path

import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from xgboost import XGBClassifier

from dashboard.lib.model import ModelArtifact
from ingestion.db.connection import get_connection
from models.data import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    build_splits,
)
from models.evaluation import evaluate

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "dashboard" / "data"
SQLITE_PATH = OUTPUT_DIR / "ipl.sqlite"
MODEL_PATH = OUTPUT_DIR / "model.pkl"

# Tables to mirror from Postgres into SQLite.
# Format: (postgres_qualified_name, sqlite_flat_name, sql_for_postgres)
TABLES = [
    (
        "gold.fact_matches",
        "gold__fact_matches",
        "SELECT * FROM gold.fact_matches",
    ),
    (
        "gold.upcoming_ipl_matches",
        "gold__upcoming_ipl_matches",
        "SELECT * FROM gold.upcoming_ipl_matches",
    ),
    (
        "gold.dim_teams",
        "gold__dim_teams",
        "SELECT * FROM gold.dim_teams",
    ),
    (
        "gold.dim_venues",
        "gold__dim_venues",
        "SELECT * FROM gold.dim_venues",
    ),
    (
        "features.features__match_set",
        "features__match_set",
        "SELECT * FROM features.features__match_set",
    ),
]


def export_sqlite() -> None:
    """Copy gold + features tables from Postgres to a single SQLite file."""
    if SQLITE_PATH.exists():
        SQLITE_PATH.unlink()
        logger.info("Removed existing SQLite at %s", SQLITE_PATH)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sqlite_conn = sqlite3.connect(str(SQLITE_PATH))

    try:
        with get_connection() as pg_conn:
            for postgres_name, sqlite_name, query in TABLES:
                df = pd.read_sql(query, pg_conn)
                df.to_sql(sqlite_name, sqlite_conn, if_exists="replace", index=False)
                logger.info(
                    "Exported %s -> %s (%d rows)",
                    postgres_name,
                    sqlite_name,
                    len(df),
                )
    finally:
        sqlite_conn.commit()
        sqlite_conn.close()

    size_kb = SQLITE_PATH.stat().st_size / 1024
    logger.info("Wrote %s (%.1f KB)", SQLITE_PATH, size_kb)


def train_and_pickle_model() -> None:
    """Train the calibrated XGBoost on full train+val, pickle to disk.

    Hyperparameters use the best from Phase 6's grid search:
    n_estimators=50, max_depth=3, learning_rate=0.05, min_child_weight=1.
    """
    logger.info("Training calibrated XGBoost for dashboard deployment...")

    train, val, holdout, encoder = build_splits()
    logger.info(
        "Loaded splits: train=%d val=%d holdout=%d",
        train.X.shape[0],
        val.X.shape[0],
        holdout.X.shape[0],
    )

    base = XGBClassifier(
        n_estimators=50,
        max_depth=3,
        learning_rate=0.05,
        min_child_weight=1,
        tree_method="hist",
        eval_metric="logloss",
        random_state=42,
        n_jobs=1,
    )
    classifier = CalibratedClassifierCV(estimator=base, method="sigmoid", cv=3)
    classifier.fit(train.X, train.y)

    # Holdout metrics for documentation.
    holdout_preds = classifier.predict_proba(holdout.X)[:, 1]
    metrics = evaluate(holdout.y, holdout_preds)
    logger.info("Holdout metrics: %s", metrics.to_dict())

    artifact = ModelArtifact(
        classifier=classifier,
        encoder=encoder,
        numeric_features=NUMERIC_FEATURES,
        categorical_features=CATEGORICAL_FEATURES,
        feature_names=train.feature_names,
        training_holdout_metrics=metrics.to_dict(),
    )

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(artifact, f)

    size_kb = MODEL_PATH.stat().st_size / 1024
    logger.info("Wrote %s (%.1f KB)", MODEL_PATH, size_kb)


def export_holdout_predictions() -> None:
    """Run the trained model on the holdout split and store predictions.

    The Calibration page reads this table to render the reliability diagram
    without re-running the model on every page load.
    """
    logger.info("Computing holdout predictions for calibration page...")

    train, val, holdout, encoder = build_splits()

    # Re-instantiate the same model architecture used in
    # train_and_pickle_model(). build_splits() is deterministic, so a fresh
    # fit produces the same calibrated classifier.
    base = XGBClassifier(
        n_estimators=50,
        max_depth=3,
        learning_rate=0.05,
        min_child_weight=1,
        tree_method="hist",
        eval_metric="logloss",
        random_state=42,
        n_jobs=1,
    )
    classifier = CalibratedClassifierCV(estimator=base, method="sigmoid", cv=3)
    classifier.fit(train.X, train.y)

    holdout_proba = classifier.predict_proba(holdout.X)[:, 1]

    # Pull the team/venue/date metadata for these match_ids from gold.
    holdout_ids_str = ",".join(f"'{mid}'" for mid in holdout.match_ids)
    metadata_query = f"""
        SELECT match_id, match_date, team_home, team_away, venue,
               batting_first_won
        FROM gold.fact_matches
        WHERE match_id IN ({holdout_ids_str})
    """
    with get_connection() as conn:
        metadata_df = pd.read_sql(metadata_query, conn)

    # Build the predictions DataFrame by joining match_ids with predictions.
    predictions_df = pd.DataFrame(
        {
            "match_id": holdout.match_ids,
            "predicted_probability": holdout_proba,
            "actual_outcome": holdout.y,
        }
    )

    df = predictions_df.merge(metadata_df, on="match_id", how="left")
    # Ensure the column order is stable for the Calibration page.
    df = df[
        [
            "match_id",
            "match_date",
            "team_home",
            "team_away",
            "venue",
            "predicted_probability",
            "actual_outcome",
        ]
    ]

    # Write to SQLite (for Streamlit Cloud deployment)
    sqlite_conn = sqlite3.connect(str(SQLITE_PATH))
    try:
        df.to_sql(
            "holdout_predictions",
            sqlite_conn,
            if_exists="replace",
            index=False,
        )
    finally:
        sqlite_conn.commit()
        sqlite_conn.close()

    # Also write to Postgres (so the dashboard works in local Postgres mode too)
    import os

    from sqlalchemy import create_engine

    pg_url = (
        f"postgresql+psycopg://{os.getenv('POSTGRES_USER')}:"
        f"{os.getenv('POSTGRES_PASSWORD')}@"
        f"{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT', '5432')}/"
        f"{os.getenv('POSTGRES_DB')}"
    )
    engine = create_engine(pg_url)
    with engine.begin() as conn:
        df.to_sql(
            "holdout_predictions",
            conn,
            if_exists="replace",
            index=False,
            schema="public",
        )

    logger.info("Wrote holdout_predictions table (%d rows) to both SQLite and Postgres", len(df))


def main() -> None:
    logger.info("Building dashboard assets...")
    export_sqlite()
    train_and_pickle_model()
    export_holdout_predictions()
    logger.info("Done. Commit dashboard/data/ to deploy.")


if __name__ == "__main__":
    main()
