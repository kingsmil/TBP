"""Advanced forecasting (Phase 5).

A deliberately simple PSF forecaster: ordinary least-squares linear trend over
the monthly median-PSF series, with a confidence band derived from the residual
standard deviation. This is a transparent, testable baseline; richer models
(seasonality, ARIMA) can replace `_fit_trend` later without changing callers.

Like appreciation, this is a heuristic aid, not financial advice.
"""
from __future__ import annotations

import numpy as np

from app.repositories.base import Repository
from app.services.analytics import estate_analytics, block_analytics

MIN_POINTS = 4          # need a few months before a trend is meaningful
CONFIDENCE_Z = 1.96     # ~95% band

DISCLAIMER = ("Heuristic linear projection for comparison only. Not financial "
              "advice; actual prices may differ materially.")


def _add_months(month: str, n: int) -> str:
    """Increment a 'YYYY-MM-01' string by n months."""
    year, mon, _ = (int(x) for x in month.split("-"))
    idx = (year * 12 + (mon - 1)) + n
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}-01"


def _fit_trend(y: list[float]) -> tuple[float, float, float, float]:
    """Return slope, intercept, residual_std, r_squared for y over x=0..n-1."""
    x = np.arange(len(y), dtype=float)
    yv = np.asarray(y, dtype=float)
    slope, intercept = np.polyfit(x, yv, 1)
    pred = slope * x + intercept
    resid = yv - pred
    resid_std = float(np.std(resid, ddof=1)) if len(y) > 2 else 0.0
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((yv - yv.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return float(slope), float(intercept), resid_std, r2


def forecast_series(monthly: list[dict], horizon_months: int = 12) -> dict | None:
    points = [(r["month"], r["median_psf"]) for r in monthly
              if r.get("median_psf") is not None]
    if len(points) < MIN_POINTS:
        return None
    months = [m for m, _ in points]
    y = [v for _, v in points]
    slope, intercept, resid_std, r2 = _fit_trend(y)

    n = len(y)
    last_month = months[-1]
    projected = []
    for h in range(1, horizon_months + 1):
        idx = n - 1 + h
        psf = slope * idx + intercept
        margin = CONFIDENCE_Z * resid_std
        projected.append({
            "month": _add_months(last_month, h),
            "psf": round(psf, 2),
            "lower": round(psf - margin, 2),
            "upper": round(psf + margin, 2),
        })
    return {
        "current_psf": round(y[-1], 2),
        "slope_per_month": round(slope, 4),
        "r_squared": round(r2, 4),
        "horizon_months": horizon_months,
        "projected_psf": projected[-1]["psf"],
        "projection": projected,
        "disclaimer": DISCLAIMER,
    }


def block_forecast(repo: Repository, block_id: int, flat_type: str | None = None,
                   horizon_months: int = 12) -> dict | None:
    a = block_analytics(repo, block_id, flat_type)
    if a is None:
        return None
    fc = forecast_series(a["psf_over_time"], horizon_months)
    if fc is None:
        return None
    return {"scope": "block", "block_id": block_id, **fc}


def estate_forecast(repo: Repository, planning_area_id: int,
                    flat_type: str | None = None,
                    horizon_months: int = 12) -> dict | None:
    a = estate_analytics(repo, planning_area_id, flat_type)
    if a is None:
        return None
    fc = forecast_series(a["psf_over_time"], horizon_months)
    if fc is None:
        return None
    return {"scope": "estate", "planning_area_id": planning_area_id, **fc}
