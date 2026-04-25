"""Train and evaluate a logistic regression classifier with calibration.

Run with:
    python -m models.train_logistic

Pipeline:
    SimpleImputer(strategy='mean')   # NULL form/h2h → mean of training set
    -> StandardScaler                # zero mean, unit variance per feature
    -> LogisticRegression            # the actual classifier
    -> CalibratedClassifierCV(cv=3)  # Platt scaling on training cross-folds

Logs to ./mlruns alongside the baseline run for side-by-side comparison.
"""

from __future__ import annotations

import logging

import mlflow
from sklearn.calibration import CalibratedClassifierCV
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from models.data import build_splits
from models.evaluation import evaluate

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

EXPERIMENT_NAME = "ipl-batting-first-won"


def build_lr_pipeline() -> CalibratedClassifierCV:
    """Build the full LR + calibration pipeline.

    Imputation strategy: mean (per ADR-007 conventions for linear models).
    Scaling: StandardScaler so coefficients are interpretable across features.
    Calibration: Platt scaling via 3-fold CV on training data.
    """
    base_pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="mean")),
            ("scaler", StandardScaler()),
            ("classifier", LogisticRegression(max_iter=1000, random_state=42)),
        ]
    )

    # CalibratedClassifierCV will fit base_pipeline on 2/3 of training data per
    # fold, then fit a sigmoid calibrator on the remaining 1/3.
    return CalibratedClassifierCV(
        estimator=base_pipeline,
        method="sigmoid",  # Platt scaling
        cv=3,
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

    with mlflow.start_run(run_name="logistic_regression_calibrated"):
        # Build and fit
        model = build_lr_pipeline()
        model.fit(train.X, train.y)

        # Log params for run comparability
        mlflow.log_param("model_type", "logistic_regression")
        mlflow.log_param("imputation", "mean")
        mlflow.log_param("scaling", "standard")
        mlflow.log_param("calibration", "platt_sigmoid")
        mlflow.log_param("cv_folds", 3)

        # Evaluate on each split
        for split_name, split in [("train", train), ("val", val), ("holdout", holdout)]:
            preds = model.predict_proba(split.X)[:, 1]
            metrics = evaluate(split.y, preds)

            logger.info("%s: %s", split_name, metrics.to_dict())

            for key, value in metrics.to_dict().items():
                mlflow.log_metric(f"{split_name}_{key}", value)

        logger.info("Run logged to MLflow at ./mlruns")


if __name__ == "__main__":
    main()
