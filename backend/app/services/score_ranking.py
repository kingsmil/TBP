"""Score Ranking — user-weighted, extensible property ranking.

The user assigns a weight to each scoring FIELD (via sliders in the UI); the
engine produces a 0-100 sub-score per field for every block, blends them with a
weight-normalized mean (unsupplied or zero-weight fields are excluded — same PRD
rule as the lifestyle/appreciation engines), and ranks blocks best-first.

Extensibility is the point: a new factor is **one entry in FIELDS** plus its
`scorer` reading from the shared per-block `BlockEval` bundle. The field list is
exposed over the API (`GET /score-ranking/fields`) so the UI builds its sliders
dynamically and never has to be edited when a field is added.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.repositories.base import Repository
from app.services.accessibility import block_accessibility
from app.services.analytics import remaining_lease_years
from app.services.appreciation import appreciation
from app.services.commute.models import Destination
from app.services.commute.optimizer import commute_burden, commute_score
from app.services.commute.provider import CommuteProvider
from app.services.lifestyle import affordability_score
from app.services.scoring import rising, weighted_normalized
from app.services.stats import summarize

# Remaining-lease band (matches the appreciation engine).
LEASE_FLOOR, LEASE_CEIL = 40, 99


# ── Per-block evidence (computed once, shared across field scorers) ────────────

@dataclass
class BlockEval:
    """Raw per-block inputs a field scorer may read. Only the pieces needed by
    the active fields are populated (the rest stay None)."""
    block_id: int
    accessibility: dict | None = None
    appreciation_score: float | None = None
    median_area_sqm: float | None = None
    transport_score: float | None = None
    affordability: float | None = None
    remaining_lease: int | None = None


# ── Field registry ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ScoreField:
    key: str
    label: str
    description: str
    default_weight: float = 50.0
    needs_destinations: bool = False
    coming_soon: bool = False
    # 0..100 sub-score for a block, or None when not applicable (excluded).
    scorer: Callable[["ScoreContext", BlockEval], float | None] | None = None

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "description": self.description,
            "default_weight": self.default_weight,
            "needs_destinations": self.needs_destinations,
            "coming_soon": self.coming_soon,
        }


def _convenience(_ctx: "ScoreContext", ev: BlockEval) -> float | None:
    if ev.accessibility is None:
        return None
    return round((ev.accessibility["mrt_score"] + ev.accessibility["bus_score"]) / 2, 2)


def _schools(_ctx: "ScoreContext", ev: BlockEval) -> float | None:
    return ev.accessibility["school_score"] if ev.accessibility else None


def _size(ctx: "ScoreContext", ev: BlockEval) -> float | None:
    if ev.median_area_sqm is None or ctx.area_bounds is None:
        return None
    lo, hi = ctx.area_bounds
    return rising(ev.median_area_sqm, lo, hi)  # bigger = higher


def _lease(_ctx: "ScoreContext", ev: BlockEval) -> float | None:
    if ev.remaining_lease is None:
        return None
    return rising(float(ev.remaining_lease), LEASE_FLOOR, LEASE_CEIL)


# Ordered registry. Add a new factor here + (if it needs new raw data) a field
# on BlockEval populated in _evaluate_block — nothing else changes.
FIELDS: tuple[ScoreField, ...] = (
    ScoreField(
        "transport", "Transport to your places",
        "How light the weekly commute is to the places you go, weighted by how "
        "often you travel there (round trips per week).",
        needs_destinations=True,
        scorer=lambda _ctx, ev: ev.transport_score,
    ),
    ScoreField(
        "appreciation", "Future appreciation",
        "Estimated potential for the block's value to grow (heuristic, not "
        "financial advice).",
        scorer=lambda _ctx, ev: ev.appreciation_score,
    ),
    ScoreField(
        "size", "Size",
        "Bigger homes score higher, based on the block's median floor area.",
        scorer=_size,
    ),
    ScoreField(
        "convenience", "MRT & bus convenience",
        "Closeness and density of MRT stations and bus stops.",
        scorer=_convenience,
    ),
    ScoreField(
        "schools", "Schools",
        "Number and closeness of nearby schools.",
        scorer=_schools,
    ),
    ScoreField(
        "value", "Value for money",
        "Cheaper relative to the rest of the market (lower median PSF) scores "
        "higher.",
        scorer=lambda _ctx, ev: ev.affordability,
    ),
    ScoreField(
        "lease", "Remaining lease",
        "Longer remaining lease scores higher.",
        scorer=_lease,
    ),
    ScoreField(
        "amenities", "Amenities (shops & food)",
        "Malls, supermarkets, hawker centres and clinics nearby. Coming soon — "
        "pending a points-of-interest dataset.",
        default_weight=0.0,
        coming_soon=True,
    ),
)

_FIELDS_BY_KEY: dict[str, ScoreField] = {f.key: f for f in FIELDS}


def list_fields() -> list[dict]:
    return [f.to_dict() for f in FIELDS]


# ── Scoring context (dataset-level, computed once) ─────────────────────────────

@dataclass
class ScoreContext:
    repo: Repository
    provider: CommuteProvider | None
    destinations: list[Destination] | None
    active_keys: frozenset[str]
    current_year: int | None
    psf_bounds: tuple[float, float] | None
    area_bounds: tuple[float, float] | None


def _block_median_area(repo: Repository, block_id: int) -> float | None:
    txns = list(repo.transactions_for_block(block_id))
    if not txns:
        return None
    areas = sorted(t.floor_area_sqm for t in txns)
    n = len(areas)
    mid = n // 2
    return areas[mid] if n % 2 else (areas[mid - 1] + areas[mid]) / 2


def _dataset_bounds(repo: Repository) -> tuple[tuple[float, float] | None,
                                                tuple[float, float] | None]:
    """(psf_bounds, area_bounds) across blocks, computed once."""
    psfs: list[float] = []
    areas: list[float] = []
    for b in repo.blocks():
        s = summarize(repo.transactions_for_block(b.block_id))
        if s.median_psf is not None:
            psfs.append(s.median_psf)
        area = _block_median_area(repo, b.block_id)
        if area is not None:
            areas.append(area)
    psf_bounds = (min(psfs), max(psfs)) if psfs else None
    area_bounds = (min(areas), max(areas)) if areas else None
    return psf_bounds, area_bounds


def _evaluate_block(ctx: ScoreContext, block_id: int) -> BlockEval:
    """Populate only the raw inputs the active fields need."""
    ev = BlockEval(block_id=block_id)
    keys = ctx.active_keys

    if "convenience" in keys or "schools" in keys:
        ev.accessibility = block_accessibility(ctx.repo, block_id)

    if "appreciation" in keys:
        appr = appreciation(ctx.repo, block_id, ctx.current_year)
        ev.appreciation_score = appr["appreciation_score"] if appr else None

    if "size" in keys:
        ev.median_area_sqm = _block_median_area(ctx.repo, block_id)

    if "value" in keys:
        ev.affordability = affordability_score(ctx.repo, block_id, ctx.psf_bounds)

    if "lease" in keys:
        block = ctx.repo.block(block_id)
        if block is not None:
            ev.remaining_lease = remaining_lease_years(
                block.lease_commencement_year, ctx.current_year)

    if "transport" in keys and ctx.provider is not None and ctx.destinations:
        block = ctx.repo.block(block_id)
        if block is not None:
            try:
                weekly = commute_burden(ctx.provider, block.point,
                                        ctx.destinations)["weekly_minutes"]
                ev.transport_score = commute_score(weekly)
            except Exception:
                # Routing provider unavailable (e.g. expired OneMap token) —
                # exclude transport rather than failing the whole ranking.
                ev.transport_score = None

    return ev


def _clean_weights(weights: dict[str, float] | None) -> dict[str, float]:
    """Keep only known, enabled fields with a positive weight."""
    out: dict[str, float] = {}
    for key, w in (weights or {}).items():
        f = _FIELDS_BY_KEY.get(key)
        if f is None or f.coming_soon:
            continue
        try:
            wf = float(w)
        except (TypeError, ValueError):
            continue
        if wf > 0:
            out[key] = wf
    return out


def rank(repo: Repository, weights: dict[str, float] | None = None,
         provider: CommuteProvider | None = None,
         destinations: list[Destination] | None = None,
         limit: int = 20, current_year: int | None = None) -> dict:
    """Rank all blocks by the user's weighted factor mix, best-first."""
    active = _clean_weights(weights)
    if not active:
        return {"count": 0, "results": [], "fields": list_fields(),
                "weights": {}}

    need_value = "value" in active
    need_size = "size" in active
    psf_bounds, area_bounds = (_dataset_bounds(repo)
                               if (need_value or need_size) else (None, None))

    ctx = ScoreContext(
        repo=repo, provider=provider, destinations=destinations,
        active_keys=frozenset(active), current_year=current_year,
        psf_bounds=psf_bounds, area_bounds=area_bounds,
    )

    results = []
    for b in repo.blocks():
        ev = _evaluate_block(ctx, b.block_id)
        breakdown: dict[str, float] = {}
        for key in active:
            scorer = _FIELDS_BY_KEY[key].scorer
            val = scorer(ctx, ev) if scorer else None
            if val is not None:
                breakdown[key] = val
        overall = weighted_normalized(breakdown, active)
        if overall is None:
            continue
        results.append({
            "block_id": b.block_id,
            "block_number": b.block_number,
            "street_name": b.street_name,
            "town": b.town,
            "planning_area_id": b.planning_area_id,
            "lon": b.point.lon,
            "lat": b.point.lat,
            "overall_score": overall,
            "breakdown": breakdown,
        })

    results.sort(key=lambda r: -r["overall_score"])
    for i, r in enumerate(results[:limit], start=1):
        r["rank"] = i
    return {
        "count": len(results),
        "results": results[:limit],
        "fields": list_fields(),
        "weights": active,
    }
