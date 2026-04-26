"""Calibration analysis: reliability diagrams + ECE for all three models.

Run with:
    python -m models.calibration_analysis

For each model (baseline, LR, XGBoost), compute predictions on holdout,
compute calibration statistics, and produce a single reliability diagram
showing all three curves overlaid.

Output:
- docs/img/calibration_holdout.png
- Logged to MLflow under run name "calibration_analysis"

The diagram is intended to make the calibration story visual: tree-based
models with peaked probability outputs vs linear models with smoother
probabilities.
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import mlflow
import numpy as np
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from models.baseline import MajorityClassBaseline
from models.data import build_splits
from models.evaluation import evaluate

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

EXPERIMENT_NAME = "ipl-batting-first-won"
OUTPUT_DIR = Path("docs/img")
OUTPUT_FILE = OUTPUT_DIR / "calibration_holdout.png"


def expected_calibration_error(
    y_true: np.ndarray, y_pred_proba: np.ndarray, n_bins: int = 10
) -> float:
    """Compute ECE: weighted average gap between predicted prob and observed frequency.

    Lower is better. Perfectly calibrated model has ECE = 0.
    """
    bin_edges = np.linspace(0, 1, n_bins + 1)
    bin_indices = np.digitize(y_pred_proba, bin_edges[1:-1])

    ece = 0.0
    n = len(y_true)
    for b in range(n_bins):
        mask = bin_indices == b
        if mask.sum() == 0:
            continue
        bin_acc = y_true[mask].mean()
        bin_conf = y_pred_proba[mask].mean()
        bin_weight = mask.sum() / n
        ece += bin_weight * abs(bin_acc - bin_conf)
    return ece


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

    # --- Train all three models on the same train data ---

    # Baseline
    baseline = MajorityClassBaseline().fit(train.X, train.y)
    baseline_holdout_preds = baseline.predict_proba_positive(holdout.X)

    # Logistic regression with calibration
    lr_pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="mean")),
            ("scaler", StandardScaler()),
            ("classifier", LogisticRegression(max_iter=1000, random_state=42)),
        ]
    )
    lr_calibrated = CalibratedClassifierCV(estimator=lr_pipeline, method="sigmoid", cv=3)
    lr_calibrated.fit(train.X, train.y)
    lr_holdout_preds = lr_calibrated.predict_proba(holdout.X)[:, 1]

    # XGBoost with calibration (use the best hyperparams from chunk 6.3)
    xgb_base = XGBClassifier(
        n_estimators=50,
        max_depth=3,
        learning_rate=0.05,
        min_child_weight=1,
        tree_method="hist",
        eval_metric="logloss",
        random_state=42,
        n_jobs=1,
    )
    xgb_calibrated = CalibratedClassifierCV(estimator=xgb_base, method="sigmoid", cv=3)
    xgb_calibrated.fit(train.X, train.y)
    xgb_holdout_preds = xgb_calibrated.predict_proba(holdout.X)[:, 1]

    # --- Compute calibration statistics ---

    models = [
        ("baseline", baseline_holdout_preds, "lightgray"),
        ("logistic_regression", lr_holdout_preds, "tab:blue"),
        ("xgboost", xgb_holdout_preds, "tab:orange"),
    ]

    stats = {}
    for name, preds, _color in models:
        metrics = evaluate(holdout.y, preds)
        ece = expected_calibration_error(holdout.y, preds, n_bins=10)
        stats[name] = {
            "accuracy": metrics.accuracy,
            "brier_score": metrics.brier_score,
            "log_loss": metrics.log_loss,
            "roc_auc": metrics.roc_auc,
            "ece": ece,
        }
        logger.info(
            "%s holdout: accuracy=%.3f brier=%.4f ece=%.4f roc_auc=%.3f",
            name,
            metrics.accuracy,
            metrics.brier_score,
            ece,
            metrics.roc_auc,
        )

    # --- Plot reliability diagram ---

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 7))

    # Diagonal reference line
    ax.plot([0, 1], [0, 1], color="black", linestyle="--", linewidth=1, label="perfect calibration")

    for name, preds, color in models:
        # Use 5 bins for our small dataset (102 holdout matches)
        prob_true, prob_pred = calibration_curve(holdout.y, preds, n_bins=5, strategy="quantile")
        ax.plot(
            prob_pred,
            prob_true,
            marker="o",
            linewidth=2,
            color=color,
            label=f"{name} (brier={stats[name]['brier_score']:.3f})",
        )

    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Observed frequency")
    ax.set_title("Reliability diagram: holdout (102 matches)")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend(loc="upper left")
    ax.grid(alpha=0.3)
    fig.tight_layout()

    fig.savefig(OUTPUT_FILE, dpi=120)
    logger.info("Saved reliability diagram to %s", OUTPUT_FILE)
    plt.close(fig)

    # --- Log to MLflow ---

    with mlflow.start_run(run_name="calibration_analysis"):
        mlflow.log_param("analysis", "reliability_diagram_holdout")
        for name, model_stats in stats.items():
            for stat_name, value in model_stats.items():
                mlflow.log_metric(f"{name}_holdout_{stat_name}", float(value))
        mlflow.log_artifact(str(OUTPUT_FILE), artifact_path="calibration")
        logger.info("Run logged to MLflow at ./mlruns")


if __name__ == "__main__":
    main()
