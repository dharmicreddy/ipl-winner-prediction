"""Train and evaluate XGBoost classifier with hyperparameter tuning.

Run with:
    python -m models.train_xgboost

Pipeline:
- XGBoost handles NaN natively via missing-value branches; no imputation
- Grid search across n_estimators, max_depth, learning_rate, min_child_weight
- Selection metric: val_brier_score (lower better) — picks best-calibrated model
- After selection: refit on full train + Platt calibration via 3-fold CV
- Final evaluation on train, val, holdout

Logs best run to ./mlruns alongside baseline and logistic_regression runs.
"""

from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass

import mlflow
from sklearn.calibration import CalibratedClassifierCV
from xgboost import XGBClassifier

from models.data import build_splits
from models.evaluation import evaluate

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

EXPERIMENT_NAME = "ipl-batting-first-won"


@dataclass(frozen=True)
class HyperParams:
    n_estimators: int
    max_depth: int
    learning_rate: float
    min_child_weight: int


# Grid: 3 × 2 × 2 × 2 = 24 combinations
HYPERPARAM_GRID = [
    HyperParams(n_estimators=n, max_depth=d, learning_rate=lr, min_child_weight=mcw)
    for n, d, lr, mcw in itertools.product(
        [50, 100, 200],
        [3, 5],
        [0.05, 0.1],
        [1, 5],
    )
]


def build_xgb(hp: HyperParams) -> XGBClassifier:
    """Build an XGBoost classifier with the given hyperparameters.

    Notes:
    - tree_method='hist' enables fast histogram-based training and native NaN handling
    - random_state=42 for reproducibility
    - eval_metric='logloss' aligns the internal training metric with our calibration goal
    - use_label_encoder=False since we already pass int labels
    """
    return XGBClassifier(
        n_estimators=hp.n_estimators,
        max_depth=hp.max_depth,
        learning_rate=hp.learning_rate,
        min_child_weight=hp.min_child_weight,
        tree_method="hist",
        eval_metric="logloss",
        random_state=42,
        n_jobs=1,
    )


def main() -> None:
    mlflow.set_tracking_uri("./mlruns")
    mlflow.set_experiment(EXPERIMENT_NAME)

    train, val, holdout, _encoder = build_splits()
    logger.info(
        "Loaded splits: train=%d val=%d holdout=%d",
        train.X.shape[0],
        val.X.shape[0],
        holdout.X.shape[0],
    )

    # Phase 1: search the grid for the best hyperparameters by val brier_score.
    logger.info("Searching %d hyperparameter combinations...", len(HYPERPARAM_GRID))

    results = []
    for hp in HYPERPARAM_GRID:
        model = build_xgb(hp)
        model.fit(train.X, train.y)
        val_preds = model.predict_proba(val.X)[:, 1]
        val_metrics = evaluate(val.y, val_preds)
        results.append((hp, val_metrics))

    # Sort by brier_score ascending (lower is better-calibrated)
    results.sort(key=lambda x: x[1].brier_score)
    best_hp, best_val_metrics = results[0]
    logger.info(
        "Best hyperparameters: %s -> val brier=%.4f, val accuracy=%.4f, val roc_auc=%.4f",
        best_hp,
        best_val_metrics.brier_score,
        best_val_metrics.accuracy,
        best_val_metrics.roc_auc,
    )

    # Phase 2: refit on full train data with Platt calibration via 3-fold CV.
    logger.info("Refitting best model on full train + calibrating...")
    base = build_xgb(best_hp)
    calibrated = CalibratedClassifierCV(estimator=base, method="sigmoid", cv=3)
    calibrated.fit(train.X, train.y)

    # Phase 3: final evaluation across all splits.
    with mlflow.start_run(run_name="xgboost_calibrated"):
        mlflow.log_param("model_type", "xgboost")
        mlflow.log_param("imputation", "native_nan")
        mlflow.log_param("calibration", "platt_sigmoid")
        mlflow.log_param("cv_folds", 3)
        mlflow.log_param("grid_size", len(HYPERPARAM_GRID))
        mlflow.log_param("n_estimators", best_hp.n_estimators)
        mlflow.log_param("max_depth", best_hp.max_depth)
        mlflow.log_param("learning_rate", best_hp.learning_rate)
        mlflow.log_param("min_child_weight", best_hp.min_child_weight)

        for split_name, split in [("train", train), ("val", val), ("holdout", holdout)]:
            preds = calibrated.predict_proba(split.X)[:, 1]
            metrics = evaluate(split.y, preds)

            logger.info("%s: %s", split_name, metrics.to_dict())

            for key, value in metrics.to_dict().items():
                mlflow.log_metric(f"{split_name}_{key}", value)

        # Log top-10 hyperparam results as run notes for reference
        top_10 = "\n".join(
            f"{i + 1}. {hp} -> brier={m.brier_score:.4f} acc={m.accuracy:.4f}"
            for i, (hp, m) in enumerate(results[:10])
        )
        mlflow.set_tag("top_10_grid_results", top_10)

        logger.info("Run logged to MLflow at ./mlruns")


if __name__ == "__main__":
    main()
