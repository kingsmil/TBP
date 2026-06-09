"""SageMaker inference handler for the PSF forecasting endpoint.

SageMaker's sklearn container calls model_fn(), input_fn(), predict_fn(),
and output_fn() in sequence for each request.

Request body (JSON):
  {"historical_psf": [float, ...], "horizon_months": int}

Response body (JSON):
  {
    "projected_psf":   float,
    "slope_per_month": float,
    "r_squared":       float,
    "projection": [
      {"month": "YYYY-MM-01", "psf": float, "lower": float, "upper": float},
      ...
    ]
  }
"""
from __future__ import annotations

import io
import json
import os
import pickle
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


# ── Model loading ─────────────────────────────────────────────────────────────

def model_fn(model_dir: str) -> dict[str, Any]:
    model_path = os.path.join(model_dir, "model.pkl")
    meta_path  = os.path.join(model_dir, "meta.json")

    with open(model_path, "rb") as f:
        model = pickle.load(f)

    with open(meta_path) as f:
        meta = json.load(f)

    return {"model": model, "meta": meta}


# ── Feature engineering (mirrors train.py) ────────────────────────────────────

def _build_future_features(
    historical_psf: list[float],
    horizon_months: int,
) -> pd.DataFrame:
    """Build a feature dataframe for the horizon months to be predicted."""
    n_hist = len(historical_psf)
    # We need at least 6 months of history for lag features.
    padded = [historical_psf[0]] * max(0, 6 - n_hist) + list(historical_psf)

    rows = []
    base_month_idx = n_hist + 1
    for h in range(1, horizon_months + 1):
        idx = base_month_idx + h
        # For future months we can't use real lags — use the last known values.
        lag_1 = padded[-1] if h == 1 else rows[-1]["psf_hat"]
        lag_3 = padded[-3] if h <= 3 else rows[-3]["psf_hat"]
        lag_6 = padded[-6] if h <= 6 else rows[-6]["psf_hat"]
        roll_3 = np.mean([padded[-1], padded[-2], padded[-3]])
        roll_6 = np.mean(padded[-6:])
        rows.append({
            "month_idx":    idx,
            "month_of_year": (idx % 12) + 1,
            "quarter":       ((idx % 12) // 3) + 1,
            "year":          2020 + idx // 12,
            "lag_1":         lag_1,
            "lag_3":         lag_3,
            "lag_6":         lag_6,
            "roll_3":        roll_3,
            "roll_6":        roll_6,
            "psf_hat":       0.0,   # placeholder, filled after prediction
        })

    return pd.DataFrame(rows)


def _add_month(base_month: str, n: int) -> str:
    year, mon, _ = (int(x) for x in base_month.split("-"))
    idx = (year * 12 + (mon - 1)) + n
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}-01"


# ── SageMaker handler functions ───────────────────────────────────────────────

def input_fn(request_body: str | bytes, content_type: str = "application/json") -> dict:
    if isinstance(request_body, bytes):
        request_body = request_body.decode("utf-8")
    return json.loads(request_body)


def predict_fn(input_data: dict, model_artifacts: dict[str, Any]) -> dict:
    model           = model_artifacts["model"]
    feature_cols    = model_artifacts["meta"]["feature_cols"]
    historical_psf  = [float(v) for v in input_data["historical_psf"]]
    horizon_months  = int(input_data.get("horizon_months", 12))

    if len(historical_psf) < 4:
        raise ValueError("At least 4 months of historical PSF data required.")

    df = _build_future_features(historical_psf, horizon_months)

    # Iteratively predict, filling in lag features as we go
    predictions: list[float] = []
    padded = list(historical_psf)
    for i in range(horizon_months):
        row = df.iloc[i]
        X = np.array([[row[c] for c in feature_cols]])
        pred = float(model.predict(X)[0])
        predictions.append(pred)
        padded.append(pred)
        # Update future rows' lag features
        if i + 1 < horizon_months:
            df.at[i + 1, "lag_1"]  = pred
            if i + 1 >= 2: df.at[i + 1, "lag_3"] = padded[-3]
            if i + 1 >= 5: df.at[i + 1, "lag_6"] = padded[-6]
            df.at[i + 1, "roll_3"] = np.mean(padded[-3:])
            df.at[i + 1, "roll_6"] = np.mean(padded[-6:])

    # Confidence interval: ±1.96 * historical residual std
    hist_arr = np.array(historical_psf)
    resid_std = float(np.std(hist_arr - np.mean(hist_arr))) or 10.0
    margin = 1.96 * resid_std

    # Compute approximate slope and R² from predictions
    x = np.arange(len(predictions), dtype=float)
    slope = float(np.polyfit(x, predictions, 1)[0])
    ss_tot = float(np.sum((np.array(predictions) - np.mean(predictions)) ** 2))
    r2 = 0.0 if ss_tot == 0 else 1.0 - (float(np.sum((np.array(predictions) - (slope * x + predictions[0])) ** 2)) / ss_tot)

    last_month = "2020-01-01"  # default; sagemaker_service.py adds context
    projection = [
        {
            "month": _add_month(last_month, h + 1),
            "psf":   round(p, 2),
            "lower": round(p - margin, 2),
            "upper": round(p + margin, 2),
        }
        for h, p in enumerate(predictions)
    ]

    return {
        "projected_psf":   round(predictions[-1], 2),
        "slope_per_month": round(slope, 4),
        "r_squared":       round(r2, 4),
        "projection":      projection,
    }


def output_fn(prediction: dict, accept: str = "application/json") -> str:
    return json.dumps(prediction)
