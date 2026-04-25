"""Majority-class baseline classifier.

Predicts the same probability for every match: P(batting_first_won) computed
on the training set. This is the floor any real model must beat. If
XGBoost only exceeds this by 1-2pp, the features aren't strong enough.
"""

from __future__ import annotations

import numpy as np


class MajorityClassBaseline:
    """Predicts the training-set positive rate for every match."""

    def __init__(self) -> None:
        self.prior_: float | None = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> MajorityClassBaseline:
        # Ignore X — that's the point of a baseline.
        self.prior_ = float(np.mean(y))
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.prior_ is None:
            raise RuntimeError("call fit() before predict_proba()")
        # Return shape (n, 2) like sklearn classifiers, where column 1 is positive class.
        n = X.shape[0]
        positive = np.full(n, self.prior_)
        negative = 1.0 - positive
        return np.column_stack([negative, positive])

    def predict_proba_positive(self, X: np.ndarray) -> np.ndarray:
        """Convenience: just the positive-class probability."""
        return self.predict_proba(X)[:, 1]
