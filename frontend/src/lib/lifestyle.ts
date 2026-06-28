/* ── TWEAK HERE ──────────────────────────────────────────────────────────────
 * "Lifestyle" = how many everyday amenities are within walking distance of a
 * block. The COUNTS (how many of each amenity within ~1km) are precomputed on
 * the server (block_amenity_counts). Here we turn those counts into a 0–100
 * score, applying per-type weight + diminishing returns at READ time — so you
 * can retune the numbers below with no backend recompute.
 *
 *   typeScore = min(count / enough, 1)        // 0..1 per type
 *   lifestyle = Σ(weight · typeScore) / Σ(weight) · 100   // 0..100
 *
 * `weight` = how much that amenity matters; `enough` = how many of it (within
 * the radius) is plenty. (The radius itself is set server-side — changing it is
 * the only thing that needs a recompute; see backend app/data/amenity_counts.py.)
 */
export const LIFESTYLE_AMENITIES: Record<string, { weight: number; enough: number }> = {
  hawker:    { weight: 3, enough: 3 }, // food centres / markets — everyday meals
  parks:     { weight: 2, enough: 2 }, // green space
  schools:   { weight: 2, enough: 3 }, // families
  sports:    { weight: 1, enough: 2 }, // sports & rec
  community: { weight: 1, enough: 2 }, // community clubs
  library:   { weight: 1, enough: 1 },
  hospitals: { weight: 1, enough: 1 }, // clinics / hospitals
};
/* ───────────────────────────────────────────────────────────────────────────*/

export const LIFESTYLE_TYPES = Object.keys(LIFESTYLE_AMENITIES);

/** 0–100 lifestyle score from precomputed per-amenity counts (see TWEAK). */
export function scoreFromCounts(counts: Record<string, number> | null | undefined): number | null {
  if (!counts) return null;
  let acc = 0, wsum = 0;
  for (const type of LIFESTYLE_TYPES) {
    const { weight, enough } = LIFESTYLE_AMENITIES[type];
    const count = counts[type] ?? 0;
    acc += weight * Math.min(count / enough, 1);
    wsum += weight;
  }
  return wsum > 0 ? Math.round((acc / wsum) * 100) : null;
}
