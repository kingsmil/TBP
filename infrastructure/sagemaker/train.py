"""SageMaker training script — PSF price forecasting model.

This script runs inside a SageMaker training job using the
scikit-learn managed container.  It trains a gradient-boosted model
(XGBoost via sklearn's HistGradientBoostingRegressor) on historical
HDB PSF data with engineered time features.

Usage (local smoke-test):
  python infrastructure/sagemaker/train.py \
    --model-dir /tmp/model \
    --train data/sample_psf.csv

Usage (via deploy_model.py):
  The deploy script creates a SageMaker training job that runs this file
  inside the managed sklearn container — you don't invoke it directly.

Input CSV schema (data/sample_psf.csv or data loaded from S3):
  month,median_psf,flat_type,planning_area_id
  2020-01-01,450.5,4-ROOM,1
  ...
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import TimeSeriesSplit


# ── Feature engineering ───────────────────────────────────────────────────────

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Convert a sorted monthly PSF dataframe into a feature matrix."""
    df = df.copy()
    df["month_dt"] = pd.to_datetime(df["month"])
    df["month_idx"] = (
        (df["month_dt"].dt.year - df["month_dt"].dt.year.min()) * 12
        + df["month_dt"].dt.month
    )
    df["month_of_year"] = df["month_dt"].dt.month
    df["quarter"]       = df["month_dt"].dt.quarter
    df["year"]          = df["month_dt"].dt.year
    # Lag features — previous 1, 3, 6 months
    df["lag_1"]  = df["median_psf"].shift(1)
    df["lag_3"]  = df["median_psf"].shift(3)
    df["lag_6"]  = df["median_psf"].shift(6)
    # Rolling mean
    df["roll_3"] = df["median_psf"].rolling(3).mean()
    df["roll_6"] = df["median_psf"].rolling(6).mean()
    df = df.dropna()
    return df


FEATURE_COLS = [
    "month_idx", "month_of_year", "quarter", "year",
    "lag_1", "lag_3", "lag_6", "roll_3", "roll_6",
]


# ── Training ──────────────────────────────────────────────────────────────────

def train(train_path: str, model_dir: str) -> None:
    df = pd.read_csv(train_path)
    df = df.sort_values("month").reset_index(drop=True)
    df = build_features(df)

    X = df[FEATURE_COLS].values
    y = df["median_psf"].values

    # Time-series cross-validation (no data leakage)
    tscv = TimeSeriesSplit(n_splits=5)
    mae_scores = []
    for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
        model = HistGradientBoostingRegressor(
            max_iter=300,
            learning_rate=0.05,
            max_depth=4,
            random_state=42,
        )
        model.fit(X[train_idx], y[train_idx])
        preds = model.predict(X[val_idx])
        mae = mean_absolute_error(y[val_idx], preds)
        mae_scores.append(mae)
        print(f"  Fold {fold + 1} MAE: {mae:.2f}")

    print(f"\nMean CV MAE: {np.mean(mae_scores):.2f} ± {np.std(mae_scores):.2f}")

    # Final model on all data
    final_model = HistGradientBoostingRegressor(
        max_iter=300,
        learning_rate=0.05,
        max_depth=4,
        random_state=42,
    )
    final_model.fit(X, y)

    # Persist
    Path(model_dir).mkdir(parents=True, exist_ok=True)
    model_path = os.path.join(model_dir, "model.pkl")
    with open(model_path, "wb") as f:
        pickle.dump(final_model, f)

    # Also save metadata the inference script needs
    meta = {
        "feature_cols": FEATURE_COLS,
        "mean_cv_mae": float(np.mean(mae_scores)),
    }
    with open(os.path.join(model_dir, "meta.json"), "w") as f:
        json.dump(meta, f)

    print(f"\nModel saved to {model_path}")


# ── SageMaker entrypoint ──────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir",  default=os.environ.get("SM_MODEL_DIR", "/opt/ml/model"))
    parser.add_argument("--train",      default=os.environ.get("SM_CHANNEL_TRAIN", "/opt/ml/input/data/train"))
    args = parser.parse_args()

    # SageMaker passes the channel as a directory; look for a CSV inside it.
    train_path = args.train
    if os.path.isdir(train_path):
        csvs = list(Path(train_path).glob("*.csv"))
        if not csvs:
            raise FileNotFoundError(f"No CSV found in training channel: {train_path}")
        train_path = str(csvs[0])

    train(train_path, args.model_dir)
