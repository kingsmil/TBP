"""Undervalued estate detector (Phase 5).

Fits a simple peer model — median PSF as a linear function of accessibility
across estates — then flags estates priced BELOW what their accessibility would
predict (negative residual) that also show positive historical growth. These
are "cheaper than comparable estates, yet still appreciating" candidates.

Heuristic screen, not financial advice.
"""
from __future__ import annotations

import numpy as np

from app.repositories.base import Repository
from app.services.comparison import estate_metrics
from app.services.scoring import clamp

MIN_ESTATES = 3
DISCLAIMER = ("Heuristic screen for comparison only. Not financial advice.")


def _features(repo: Repository, flat_type: str | None):
    rows = []
    for pa in repo.planning_areas():
        m = estate_metrics(repo, pa.planning_area_id, flat_type)
        if m is None:
            continue
        access = m["accessibility"]["combined_score"]
        psf = m["median_psf"]
        if access is None or psf is None:
            continue
        rows.append(m)
    return rows


def detect_undervalued(repo: Repository, flat_type: str | None = None) -> dict:
    rows = _features(repo, flat_type)
    if len(rows) < MIN_ESTATES:
        return {"undervalued": [], "note": "not enough estates to model",
                "disclaimer": DISCLAIMER}

    access = np.array([r["accessibility"]["combined_score"] for r in rows], dtype=float)
    psf = np.array([r["median_psf"] for r in rows], dtype=float)
    slope, intercept = np.polyfit(access, psf, 1)

    out = []
    for r in rows:
        a = r["accessibility"]["combined_score"]
        predicted = slope * a + intercept
        residual = r["median_psf"] - predicted          # negative => cheaper than peers
        growth = r["growth_pct"]
        discount_pct = round(-residual / predicted * 100, 2) if predicted else 0.0
        is_undervalued = residual < 0 and (growth or 0) > 0
        if not is_undervalued:
            continue
        score = round(clamp(discount_pct + (growth or 0)), 2)
        out.append({
            "planning_area_id": r["planning_area_id"],
            "name": r["name"],
            "median_psf": r["median_psf"],
            "predicted_psf": round(predicted, 2),
            "discount_vs_peers_pct": discount_pct,
            "growth_pct": growth,
            "accessibility": r["accessibility"]["combined_score"],
            "undervalued_score": score,
            "reason": (f"{discount_pct}% below accessibility-implied PSF "
                       f"with {growth}% historical growth"),
        })
    out.sort(key=lambda r: -r["undervalued_score"])
    return {"undervalued": out, "model": {"slope": round(float(slope), 4),
                                          "intercept": round(float(intercept), 2)},
            "disclaimer": DISCLAIMER}
