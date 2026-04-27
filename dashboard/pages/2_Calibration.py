"""Calibration analysis page — reliability diagram, ECE, Brier score.

Reads pre-computed holdout predictions from the SQLite snapshot (built by
scripts/build_dashboard_assets.py) and shows how well-calibrated the model's
probabilities actually are.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard.lib.data import get_backend_name, query  # noqa: E402

st.set_page_config(page_title="Calibration", page_icon="📈", layout="wide")


@st.cache_data(ttl=300)
def load_holdout_predictions() -> pd.DataFrame:
    return query("""
        SELECT match_id, match_date, team_home, team_away, venue,
               predicted_probability, actual_outcome
        FROM holdout_predictions
        ORDER BY match_date
    """)


def compute_calibration_bins(df: pd.DataFrame, n_bins: int = 10) -> pd.DataFrame:
    """Bin predictions into deciles and compute mean predicted vs actual rate."""
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_indices = np.digitize(df["predicted_probability"], bin_edges, right=True)
    bin_indices = np.clip(bin_indices, 1, n_bins)

    rows = []
    for b in range(1, n_bins + 1):
        mask = bin_indices == b
        n = int(mask.sum())
        if n == 0:
            continue
        mean_predicted = float(df.loc[mask, "predicted_probability"].mean())
        actual_rate = float(df.loc[mask, "actual_outcome"].mean())
        rows.append(
            {
                "bin": b,
                "bin_lower": bin_edges[b - 1],
                "bin_upper": bin_edges[b],
                "n_samples": n,
                "mean_predicted": mean_predicted,
                "actual_rate": actual_rate,
            }
        )
    return pd.DataFrame(rows)


def compute_ece(df: pd.DataFrame, n_bins: int = 10) -> float:
    """Expected Calibration Error: weighted mean of |mean_predicted - actual| per bin."""
    bins_df = compute_calibration_bins(df, n_bins=n_bins)
    if bins_df.empty:
        return 0.0
    bins_df["abs_diff"] = (bins_df["mean_predicted"] - bins_df["actual_rate"]).abs()
    bins_df["weight"] = bins_df["n_samples"] / bins_df["n_samples"].sum()
    return float((bins_df["abs_diff"] * bins_df["weight"]).sum())


def compute_brier_score(df: pd.DataFrame) -> float:
    """Mean squared error between predicted probability and binary actual outcome."""
    diffs = df["predicted_probability"] - df["actual_outcome"]
    return float((diffs**2).mean())


def render_reliability_chart(bins_df: pd.DataFrame) -> go.Figure:
    """Build a Plotly reliability diagram with the perfect-calibration diagonal."""
    fig = go.Figure()

    # Perfect-calibration diagonal
    fig.add_trace(
        go.Scatter(
            x=[0, 1],
            y=[0, 1],
            mode="lines",
            line=dict(color="gray", dash="dash", width=2),
            name="Perfect calibration",
            hoverinfo="skip",
        )
    )

    # Model reliability curve (sized by sample count per bin)
    fig.add_trace(
        go.Scatter(
            x=bins_df["mean_predicted"],
            y=bins_df["actual_rate"],
            mode="lines+markers",
            marker=dict(
                size=8 + 2 * np.sqrt(bins_df["n_samples"]),
                color="#FF4B4B",
                line=dict(color="white", width=1),
            ),
            line=dict(color="#FF4B4B", width=2),
            name="XGBoost (calibrated)",
            hovertemplate=(
                "Bin %{customdata[0]} of 10<br>"
                "Mean predicted: %{x:.2%}<br>"
                "Actual win rate: %{y:.2%}<br>"
                "Samples in bin: %{customdata[1]}"
                "<extra></extra>"
            ),
            customdata=np.column_stack([bins_df["bin"], bins_df["n_samples"]]),
        )
    )

    fig.update_layout(
        xaxis=dict(
            title="Mean predicted probability (per bin)",
            range=[-0.02, 1.02],
            tickformat=".0%",
        ),
        yaxis=dict(
            title="Actual win rate (per bin)",
            range=[-0.02, 1.02],
            tickformat=".0%",
        ),
        hovermode="closest",
        height=500,
        showlegend=True,
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
        margin=dict(l=60, r=20, t=20, b=60),
    )
    return fig


def main():
    st.title("📈 Calibration analysis")
    st.caption(
        f"Backend: **{get_backend_name()}** • "
        "How well-calibrated are the model's predicted probabilities?"
    )

    # ---- Intro ----
    st.markdown("""
    A well-calibrated classifier's predicted probabilities should match the actual
    rate of positive outcomes. If the model says **70% chance the home team wins**,
    then across all such predictions, the home team should actually win about 70%
    of the time. The closer the curve is to the diagonal, the better calibrated.
    """)

    df = load_holdout_predictions()
    if df.empty:
        st.warning(
            "No holdout predictions found. "
            "Run `python -m scripts.build_dashboard_assets` to generate them."
        )
        return

    bins_df = compute_calibration_bins(df, n_bins=10)
    ece = compute_ece(df, n_bins=10)
    brier = compute_brier_score(df)
    accuracy = float(
        ((df["predicted_probability"] >= 0.5).astype(int) == df["actual_outcome"]).mean()
    )

    # ---- Headline metrics ----
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Holdout matches", f"{len(df):,}")
    col2.metric("Accuracy", f"{accuracy:.1%}")
    col3.metric(
        "Brier score",
        f"{brier:.3f}",
        delta=f"{brier - 0.250:+.3f} vs baseline",
        delta_color="inverse",  # lower is better
        help=(
            "Mean squared error between predicted probability and actual outcome. "
            "Baseline (always-50/50) = 0.250."
        ),
    )
    col4.metric(
        "ECE (Expected Calibration Error)",
        f"{ece:.3f}",
        help="Weighted mean of |predicted - actual| across decile bins. Lower is better.",
    )

    st.divider()

    # ---- Reliability diagram ----
    st.subheader("Reliability diagram")
    st.caption(
        "Each marker represents one decile of predictions. "
        "Marker size scales with sample count in that bin."
    )

    fig = render_reliability_chart(bins_df)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("""
    **How to read this chart:**
    - **On the diagonal**: predicted probability matches actual win rate. Perfect calibration.
    - **Below the diagonal**: model is overconfident (predicting 70% but actual is 50%).
    - **Above the diagonal**: model is underconfident (predicting 50% but actual is 70%).
    """)

    st.divider()

    # ---- Bin table ----
    st.subheader("Per-bin breakdown")
    display_df = bins_df.copy()
    display_df["bin_range"] = display_df.apply(
        lambda r: f"[{r['bin_lower']:.0%}, {r['bin_upper']:.0%})",
        axis=1,
    )
    display_df = display_df[
        [
            "bin_range",
            "n_samples",
            "mean_predicted",
            "actual_rate",
        ]
    ].rename(
        columns={
            "bin_range": "Predicted probability range",
            "n_samples": "Matches in bin",
            "mean_predicted": "Mean predicted",
            "actual_rate": "Actual win rate",
        }
    )
    display_df["Mean predicted"] = display_df["Mean predicted"].apply(lambda v: f"{v:.1%}")
    display_df["Actual win rate"] = display_df["Actual win rate"].apply(lambda v: f"{v:.1%}")
    st.dataframe(display_df, width="stretch", hide_index=True)

    st.divider()

    # ---- Honest caveats ----
    st.subheader("Honest caveats")
    st.warning("""
    **The model is barely better than baseline on Brier score.**

    A naive classifier that always predicts 0.5 has a Brier score of 0.250. Our
    calibrated XGBoost scores 0.252 — virtually identical. The model picks up
    enough signal to beat baseline accuracy by ~10pp, but its probability
    estimates are not meaningfully sharper than uninformed guessing.

    **What this means for use:**
    - Treat probabilities as directional, not as exact odds
    - The model is honest about its uncertainty (most predictions cluster near 50%)
    - Strong predictions (>70% or <30%) are rare but more reliable when they appear

    See the full analysis in [`docs/MODEL_CARD.md`](https://github.com/dharmicreddy/ipl-winner-prediction/blob/main/docs/MODEL_CARD.md).
    """)


main()
