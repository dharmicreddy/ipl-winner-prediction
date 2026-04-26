"""Evaluation metrics for binary classification with calibration.

We track three families of metrics:

- Discriminative (does the model rank predictions correctly?):
    accuracy, ROC-AUC

- Probabilistic / calibration (are probabilities meaningful?):
    log_loss (lower better), brier_score (lower better)

The latter is what ADR-004 cares about most: predictions of "65% chance of
winning" should empirically be right ~65% of the time.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)


@dataclass
class Metrics:
    """All metrics computed for one (model, split) pair."""

    accuracy: float
    log_loss: float
    brier_score: float
    roc_auc: float
    n_samples: int

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def evaluate(y_true: np.ndarray, y_pred_proba: np.ndarray) -> Metrics:
    """Compute all metrics from probability predictions.

    Parameters
    ----------
    y_true : array of 0/1
        Ground truth labels.
    y_pred_proba : array of float in [0, 1]
        Predicted probabilities for the positive class.
    """
    # Predicted class for accuracy
    y_pred = (y_pred_proba >= 0.5).astype(int)

    return Metrics(
        accuracy=float(accuracy_score(y_true, y_pred)),
        log_loss=float(log_loss(y_true, y_pred_proba)),
        brier_score=float(brier_score_loss(y_true, y_pred_proba)),
        roc_auc=float(roc_auc_score(y_true, y_pred_proba)),
        n_samples=len(y_true),
    )
