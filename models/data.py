"""Load feature matrix from the dbt warehouse for model training.

Reads `features.features__match_set`, returns separate X/y arrays for each
walk-forward split (train, val, holdout). Encoding choices:

- Numeric features: pass through; missingness handled per-model in the
  pipeline (mean imputation for LR, sentinel -1 for XGBoost).
- Categorical features (team_home, team_away, venue): one-hot encoded.
  The encoder is fit on training data only; val/holdout transform with it
  (per ADR-007 leakage policy).
- Label: `batting_first_won` (boolean → 0/1 int).

The leakage discipline: even though X for val/holdout uses the train-fit
encoder, that's OK because team/venue identity is a stable categorical,
not derived from match outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.preprocessing import OneHotEncoder

from ingestion.db.connection import get_connection

# Numeric feature columns we feed to the model.
NUMERIC_FEATURES = [
    "team_home_form_5",
    "team_away_form_5",
    "h2h_matches_played",
    "team_home_h2h_wins",
    "team_home_h2h_win_rate",
    "venue_matches_played",
    "venue_bat_first_win_rate",
    "days_since_team_home_last_match",
    "days_since_team_away_last_match",
    "match_number_in_season",
]

# Categorical feature columns one-hot encoded.
CATEGORICAL_FEATURES = ["team_home", "team_away", "venue"]

LABEL = "batting_first_won"


@dataclass
class DataSplit:
    """One walk-forward split's data, ready for model.fit / model.predict."""

    X: np.ndarray
    y: np.ndarray
    feature_names: list[str]
    match_ids: pd.Series  # for downstream error analysis


def load_match_set() -> pd.DataFrame:
    """Pull the wide feature table from Postgres."""
    query = "SELECT * FROM features.features__match_set ORDER BY match_date"
    with get_connection() as conn:
        return pd.read_sql(query, conn)


def build_splits() -> tuple[DataSplit, DataSplit, DataSplit, OneHotEncoder]:
    """Load and split data into train, val, holdout.

    Returns
    -------
    train, val, holdout : DataSplit
    encoder : OneHotEncoder fit on train only (for downstream usage)
    """
    df = load_match_set()

    train_df = df[df["split"] == "train"].copy()
    val_df = df[df["split"] == "val"].copy()
    holdout_df = df[df["split"] == "holdout"].copy()

    # Fit encoder on train only — leakage discipline.
    encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    encoder.fit(train_df[CATEGORICAL_FEATURES])

    cat_feature_names = list(encoder.get_feature_names_out(CATEGORICAL_FEATURES))
    feature_names = NUMERIC_FEATURES + cat_feature_names

    def _to_split(part_df: pd.DataFrame) -> DataSplit:
        X_num = part_df[NUMERIC_FEATURES].to_numpy(dtype=float)
        X_cat = encoder.transform(part_df[CATEGORICAL_FEATURES])
        X = np.hstack([X_num, X_cat])
        y = part_df[LABEL].astype(int).to_numpy()
        return DataSplit(X=X, y=y, feature_names=feature_names, match_ids=part_df["match_id"])

    return _to_split(train_df), _to_split(val_df), _to_split(holdout_df), encoder
