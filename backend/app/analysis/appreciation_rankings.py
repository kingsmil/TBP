"""Appreciation ranking analysis.

Ranks every planning area ("region") and every block by historical price
appreciation over an analysis window (default 10 years), and pairs it with the
forward-looking composite appreciation score. Pure computation runs against the
Repository interface (so it is unit-testable in memory); persistence targets
PostGIS.

Headline metric: CAGR of the median PSF — the annualised growth from the first
to the last year with data inside the window:

    cagr = (psf_end / psf_start) ** (1 / (year_end - year_start)) - 1

Built on demand by `build_rankings`, persisted by `persist`, and driven by the
`app.analysis.build_rankings` CLI (run after seeding and monthly via cron).
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from app.repositories.base import Repository
from app.services.appreciation import appreciation

DEFAULT_WINDOW_YEARS = 10
# Minimum evidence to rank a unit (avoids ranking on one or two stray sales).
BLOCK_MIN_TXNS = 5
REGION_MIN_TXNS = 20
MIN_DISTINCT_YEARS = 2
# The composite appreciation score is expensive (several PostGIS queries per
# block). When computed, bound it to the top-N CAGR performers in each region.
DEFAULT_SCORE_TOP_N = 50


@dataclass
class Ranking:
    cagr_pct: float
    appreciation_score: float | None
    median_psf_start: float
    median_psf_end: float
    year_start: int
    year_end: int
    txn_count: int
    rank: int = 0


@dataclass
class BlockRanking(Ranking):
    block_id: int = 0
    planning_area_id: int | None = None
    region_rank: int = 0


@dataclass
class RegionRanking(Ranking):
    planning_area_id: int = 0
    name: str | None = None
    region: str | None = None
    block_count: int = 0


def _year(transaction_month: str) -> int:
    return int(transaction_month[:4])


def _annual_median_psf(txns) -> dict[int, float]:
    """Median PSF per calendar year."""
    by_year: dict[int, list[float]] = {}
    for t in txns:
        by_year.setdefault(_year(t.transaction_month), []).append(t.psf)
    return {y: statistics.median(v) for y, v in by_year.items() if v}


def _cagr(annual: dict[int, float], ref_year: int, years: int):
    """CAGR of median PSF over the window [ref_year-years+1, ref_year].

    Returns (cagr_pct, psf_start, psf_end, year_start, year_end) or None when
    there isn't enough span/data to compute a rate. "10 years" spans from
    10 years ago to the reference year (e.g. 2016..2026), so a full decade of
    appreciation can be measured.
    """
    lo = ref_year - years
    in_window = {y: psf for y, psf in annual.items() if lo <= y <= ref_year}
    if len(in_window) < MIN_DISTINCT_YEARS:
        return None
    year_start, year_end = min(in_window), max(in_window)
    psf_start, psf_end = in_window[year_start], in_window[year_end]
    span = year_end - year_start
    if span <= 0 or psf_start <= 0:
        return None
    cagr = (psf_end / psf_start) ** (1.0 / span) - 1.0
    return round(cagr * 100, 2), round(psf_start, 2), round(psf_end, 2), year_start, year_end


def _group_transactions(repo: Repository) -> dict[int, list]:
    """All transactions grouped by block in a single pass (one DB query)."""
    by_block: dict[int, list] = {}
    for t in repo.transactions():
        by_block.setdefault(t.block_id, []).append(t)
    return by_block


def _latest_year_from(txns_by_block: dict[int, list]) -> int | None:
    years = [_year(t.transaction_month)
             for txns in txns_by_block.values() for t in txns]
    return max(years) if years else None


def _assign_ranks(items: list, key=lambda r: (r.cagr_pct, r.appreciation_score or 0.0)) -> None:
    items.sort(key=key, reverse=True)
    for i, r in enumerate(items, start=1):
        r.rank = i


def build_block_rankings(repo: Repository, years: int = DEFAULT_WINDOW_YEARS,
                         ref_year: int | None = None, with_score: bool = False,
                         score_top_n: int | None = DEFAULT_SCORE_TOP_N,
                         txns_by_block: dict[int, list] | None = None) -> list[BlockRanking]:
    """Rank blocks by CAGR (fast). When `with_score`, also attach the composite
    appreciation score — but only for the top `score_top_n` blocks in each
    region, since that part is expensive (set score_top_n=None for all)."""
    if txns_by_block is None:
        txns_by_block = _group_transactions(repo)
    ref_year = ref_year or _latest_year_from(txns_by_block)
    if ref_year is None:
        return []
    out: list[BlockRanking] = []
    for b in repo.blocks():
        txns = txns_by_block.get(b.block_id, [])
        if len(txns) < BLOCK_MIN_TXNS:
            continue
        cagr = _cagr(_annual_median_psf(txns), ref_year, years)
        if cagr is None:
            continue
        cagr_pct, psf_start, psf_end, y0, y1 = cagr
        out.append(BlockRanking(
            block_id=b.block_id, planning_area_id=b.planning_area_id,
            cagr_pct=cagr_pct, appreciation_score=None,
            median_psf_start=psf_start, median_psf_end=psf_end,
            year_start=y0, year_end=y1, txn_count=len(txns),
        ))
    _assign_ranks(out)
    # Per-region rank (within each planning area).
    by_area: dict[int | None, list[BlockRanking]] = {}
    for r in out:
        by_area.setdefault(r.planning_area_id, []).append(r)
    for group in by_area.values():
        for i, r in enumerate(sorted(group, key=lambda r: r.rank), start=1):
            r.region_rank = i

    # (Optional) composite score — the slow pass, bounded to top-N per region.
    if with_score:
        for r in out:
            if score_top_n is not None and r.region_rank > score_top_n:
                continue
            try:
                appr = appreciation(repo, r.block_id)
                r.appreciation_score = appr["appreciation_score"] if appr else None
            except Exception:
                pass
    return out


def build_region_rankings(repo: Repository, years: int = DEFAULT_WINDOW_YEARS,
                          ref_year: int | None = None,
                          block_rankings: list[BlockRanking] | None = None,
                          txns_by_block: dict[int, list] | None = None) -> list[RegionRanking]:
    if txns_by_block is None:
        txns_by_block = _group_transactions(repo)
    ref_year = ref_year or _latest_year_from(txns_by_block)
    if ref_year is None:
        return []
    # Mean composite score per area from the block rankings (already computed).
    scores_by_area: dict[int | None, list[float]] = {}
    for br in (block_rankings or []):
        if br.appreciation_score is not None:
            scores_by_area.setdefault(br.planning_area_id, []).append(br.appreciation_score)

    blocks_by_area: dict[int, list[int]] = {}
    for b in repo.blocks():
        if b.planning_area_id is not None:
            blocks_by_area.setdefault(b.planning_area_id, []).append(b.block_id)

    areas = {pa.planning_area_id: pa for pa in repo.planning_areas()}
    out: list[RegionRanking] = []
    for pa_id, block_ids in blocks_by_area.items():
        txns = [t for bid in block_ids for t in txns_by_block.get(bid, [])]
        if len(txns) < REGION_MIN_TXNS:
            continue
        cagr = _cagr(_annual_median_psf(txns), ref_year, years)
        if cagr is None:
            continue
        cagr_pct, psf_start, psf_end, y0, y1 = cagr
        scores = scores_by_area.get(pa_id, [])
        pa = areas.get(pa_id)
        out.append(RegionRanking(
            planning_area_id=pa_id,
            name=pa.name if pa else None,
            region=pa.region if pa else None,
            cagr_pct=cagr_pct,
            appreciation_score=round(statistics.fmean(scores), 2) if scores else None,
            median_psf_start=psf_start, median_psf_end=psf_end,
            year_start=y0, year_end=y1, txn_count=len(txns),
            block_count=len(block_ids),
        ))
    _assign_ranks(out)
    return out


def build_rankings(repo: Repository, years: int = DEFAULT_WINDOW_YEARS,
                   with_score: bool = False,
                   score_top_n: int | None = DEFAULT_SCORE_TOP_N):
    """Compute both block and region rankings. Returns (blocks, regions).

    with_score=False (default) is the fast CAGR-only build for manual runs;
    with_score=True attaches the composite appreciation score (bounded to the
    top `score_top_n` blocks per region) — used by the monthly background job.
    """
    txns_by_block = _group_transactions(repo)  # one query, reused by both passes
    ref_year = _latest_year_from(txns_by_block)
    blocks = build_block_rankings(repo, years, ref_year, with_score=with_score,
                                  score_top_n=score_top_n, txns_by_block=txns_by_block)
    regions = build_region_rankings(repo, years, ref_year, block_rankings=blocks,
                                    txns_by_block=txns_by_block)
    return blocks, regions


# ── Persistence (PostGIS) ─────────────────────────────────────────────────────

def persist(engine, blocks: list[BlockRanking], regions: list[RegionRanking]) -> None:
    """Full-replace both ranking tables in a single transaction."""
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM block_appreciation_ranking"))
        conn.execute(text("DELETE FROM region_appreciation_ranking"))
        if regions:
            conn.execute(text("""
                INSERT INTO region_appreciation_ranking
                  (planning_area_id, name, region, rank, appreciation_score, cagr_pct,
                   median_psf_start, median_psf_end, year_start, year_end, txn_count, block_count)
                VALUES
                  (:planning_area_id, :name, :region, :rank, :appreciation_score, :cagr_pct,
                   :median_psf_start, :median_psf_end, :year_start, :year_end, :txn_count, :block_count)
            """), [r.__dict__ for r in regions])
        if blocks:
            conn.execute(text("""
                INSERT INTO block_appreciation_ranking
                  (block_id, planning_area_id, rank, region_rank, appreciation_score, cagr_pct,
                   median_psf_start, median_psf_end, year_start, year_end, txn_count)
                VALUES
                  (:block_id, :planning_area_id, :rank, :region_rank, :appreciation_score, :cagr_pct,
                   :median_psf_start, :median_psf_end, :year_start, :year_end, :txn_count)
            """), [{k: v for k, v in b.__dict__.items() if k != "name" and k != "region"
                    and k != "block_count"} for b in blocks])


def read_region_rankings(engine, limit: int = 50) -> list[dict]:
    from sqlalchemy import text
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT * FROM region_appreciation_ranking ORDER BY rank LIMIT :limit
        """), {"limit": limit}).mappings().all()
    return [dict(r) for r in rows]


def block_scores(engine) -> dict[int, float]:
    """All block_id -> appreciation sub-score (0-100), precomputed. Cheap bulk
    read for blending a per-block match score on the client. Prefers the composite
    appreciation_score (top-N per region); falls back to normalised CAGR so the
    full set of ranked blocks is covered."""
    from sqlalchemy import text
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT block_id, appreciation_score, cagr_pct "
            "FROM block_appreciation_ranking")).all()
    out: dict[int, float] = {}
    for r in rows:
        if r.appreciation_score is not None:
            out[int(r.block_id)] = float(r.appreciation_score)
        elif r.cagr_pct is not None:
            # ~0%/yr -> 50, +12.5%/yr -> 100, -12.5%/yr -> 0
            out[int(r.block_id)] = max(0.0, min(100.0, 50 + float(r.cagr_pct) * 4))
    return out


def read_block_rankings(engine, planning_area_id: int | None = None,
                        limit: int = 50) -> list[dict]:
    from sqlalchemy import text
    sql = """
        SELECT r.*, b.block_number, b.street_name, b.town,
               ST_Y(b.geom) AS lat, ST_X(b.geom) AS lon,
               pa.name AS planning_area_name
        FROM block_appreciation_ranking r
        LEFT JOIN hdb_blocks b ON b.block_id = r.block_id
        LEFT JOIN planning_areas pa ON pa.planning_area_id = r.planning_area_id
    """
    params: dict = {"limit": limit}
    if planning_area_id is not None:
        sql += " WHERE r.planning_area_id = :pa"
        params["pa"] = planning_area_id
    sql += " ORDER BY r.rank LIMIT :limit"
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]
