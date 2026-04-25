"""Train and evaluate the majority-class baseline.

Run with:
    python -m models.train_baseline

Logs to MLflow tracking dir at ./mlruns. View results with:
    mlflow ui --backend-store-uri ./mlruns
"""

from __future__ import annotations

import logging

import mlflow

from models.baseline import MajorityClassBaseline
from models.data import build_splits
from models.evaluation import evaluate

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

EXPERIMENT_NAME = "ipl-batting-first-won"


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

    with mlflow.start_run(run_name="baseline_majority_class"):
        # Fit
        model = MajorityClassBaseline().fit(train.X, train.y)
        mlflow.log_param("model_type", "majority_class_baseline")
        mlflow.log_param("training_prior", model.prior_)

        # Evaluate on each split
        for split_name, split in [("train", train), ("val", val), ("holdout", holdout)]:
            preds = model.predict_proba_positive(split.X)
            metrics = evaluate(split.y, preds)

            logger.info("%s: %s", split_name, metrics.to_dict())

            # Log each metric prefixed with split name (mlflow style)
            for key, value in metrics.to_dict().items():
                mlflow.log_metric(f"{split_name}_{key}", value)

        logger.info("Run logged to MLflow at ./mlruns")


if __name__ == "__main__":
    main()
