"""SageMaker real-time endpoint client for PSF price forecasting.

In production a scikit-learn / XGBoost model trained in
infrastructure/sagemaker/train.py is deployed to a SageMaker endpoint.
This module calls that endpoint and adapts its output to match the dict
shape that forecasting.py already produces, so the API routes need no changes.

Fallback behaviour: if AWS_SAGEMAKER_ENDPOINT is not set (local dev, CI) the
module raises SageMakerUnavailable and callers can fall back to the local
OLS forecaster in forecasting.py.
"""
from __future__ import annotations

import json
import os
from typing import Any

from botocore.exceptions import ClientError  # type: ignore

from app.core.aws_config import get_sagemaker_runtime

ENDPOINT_NAME = os.getenv("AWS_SAGEMAKER_ENDPOINT", "")

DISCLAIMER = (
    "SageMaker XGBoost projection for comparison only. Not financial advice; "
    "actual prices may differ materially."
)


class SageMakerUnavailable(RuntimeError):
    """Raised when the SageMaker endpoint is not configured or unreachable."""


def _require_endpoint() -> str:
    if not ENDPOINT_NAME:
        raise SageMakerUnavailable(
            "AWS_SAGEMAKER_ENDPOINT is not set. "
            "Either deploy the SageMaker model (see infrastructure/sagemaker/) "
            "or leave LLM_PROVIDER unset to use the local OLS fallback."
        )
    return ENDPOINT_NAME


def predict_psf_series(
    historical_psf: list[float],
    horizon_months: int = 12,
) -> dict[str, Any]:
    """Call the SageMaker endpoint and return a forecast dict.

    Input payload sent to the endpoint:
      {"historical_psf": [float, ...], "horizon_months": int}

    Expected response from the endpoint:
      {
        "projected_psf":  float,
        "projection":     [{"month": str, "psf": float, "lower": float, "upper": float}, ...],
        "slope_per_month": float,
        "r_squared":      float,
      }
    """
    endpoint = _require_endpoint()
    payload = json.dumps(
        {"historical_psf": historical_psf, "horizon_months": horizon_months}
    ).encode()

    try:
        resp = get_sagemaker_runtime().invoke_endpoint(
            EndpointName=endpoint,
            ContentType="application/json",
            Accept="application/json",
            Body=payload,
        )
    except ClientError as exc:
        raise SageMakerUnavailable(
            f"SageMaker endpoint '{endpoint}' returned an error: {exc}"
        ) from exc

    body: dict[str, Any] = json.loads(resp["Body"].read())

    return {
        "current_psf": round(float(historical_psf[-1]), 2) if historical_psf else 0.0,
        "slope_per_month": round(float(body.get("slope_per_month", 0.0)), 4),
        "r_squared": round(float(body.get("r_squared", 0.0)), 4),
        "horizon_months": horizon_months,
        "projected_psf": round(float(body["projected_psf"]), 2),
        "projection": [
            {
                "month": p["month"],
                "psf": round(float(p["psf"]), 2),
                "lower": round(float(p["lower"]), 2),
                "upper": round(float(p["upper"]), 2),
            }
            for p in body["projection"]
        ],
        "disclaimer": DISCLAIMER,
        "source": "sagemaker",
    }


def is_available() -> bool:
    """Return True if the endpoint name is configured (endpoint may still be cold)."""
    return bool(ENDPOINT_NAME)
