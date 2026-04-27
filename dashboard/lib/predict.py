"""Prediction glue: features + encoder + model -> calibrated probability.

Bridges the as-of feature computation with the trained ModelArtifact.
"""

from __future__ import annotations

from datetime import date

import numpy as np

from dashboard.lib.features import MatchFeatures, compute_features
from dashboard.lib.model import ModelArtifact


def features_to_array(
    features: MatchFeatures,
    team_home: str,
    team_away: str,
    venue: str,
    artifact: ModelArtifact,
) -> np.ndarray:
    """Convert a MatchFeatures + categorical inputs into the model's input array.

    Returns a 1D array shaped to match artifact.feature_names.
    """
    # Numeric features in the same order as artifact.numeric_features.
    numeric_dict = features.to_dict()
    numeric_array = np.array(
        [numeric_dict[name] for name in artifact.numeric_features],
        dtype=float,
    )

    # Categorical features: one-hot via the trained encoder.
    cat_input = np.array([[team_home, team_away, venue]], dtype=object)
    cat_array = artifact.encoder.transform(cat_input).flatten()

    return np.concatenate([numeric_array, cat_array]).reshape(1, -1)


def predict(
    target_date: date,
    team_home: str,
    team_away: str,
    venue: str,
    artifact: ModelArtifact,
) -> dict:
    """Run end-to-end prediction for a hypothetical match.

    Returns a dict with the prediction details:
        - features: MatchFeatures (the inputs)
        - probability_batting_first_wins: float in [0, 1]
        - probability_team_home_wins: float in [0, 1] (if team_home bats first)
        - prediction: str ("team_home wins" or "team_away wins")
        - confidence: str ("high" / "medium" / "low")
    """
    features = compute_features(target_date, team_home, team_away, venue)
    X = features_to_array(features, team_home, team_away, venue, artifact)

    # CalibratedClassifierCV.predict_proba returns shape (1, 2):
    # column 0 = P(batting_first_won == 0), column 1 = P(batting_first_won == 1)
    proba = artifact.classifier.predict_proba(X)[0]
    p_bat_first_wins = float(proba[1])

    # Confidence interpretation
    distance_from_50 = abs(p_bat_first_wins - 0.5)
    if distance_from_50 >= 0.20:
        confidence = "high"
    elif distance_from_50 >= 0.10:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "features": features,
        "probability_batting_first_wins": p_bat_first_wins,
        "probability_batting_second_wins": 1.0 - p_bat_first_wins,
        "confidence": confidence,
    }
