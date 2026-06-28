import type { AmenityPoi } from "../types";

/* ── TWEAK HERE ──────────────────────────────────────────────────────────────
 * "Lifestyle" = how many everyday amenities are within walking distance of a
 * block. For each amenity type we count POIs within RADIUS_KM, give partial
 * credit up to `enough` (diminishing returns — more than `enough` doesn't help),
 * weight by `weight`, then blend to a single 0–100 score.
 *
 *   typeScore = min(countWithinRadius / enough, 1)        // 0..1 per type
 *   lifestyle = Σ(weight · typeScore) / Σ(weight) · 100   // 0..100
 *
 * Edit RADIUS_KM and the weight/enough numbers to retune. `weight` = how much
 * that amenity matters; `enough` = how many of it (within the radius) is plenty.
 */
export const LIFESTYLE_RADIUS_KM = 1.0; // "within ~1 km / a short walk"

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

const toRad = (d: number) => (d * Math.PI) / 180;
function haversineKm(aLat: number, aLon: number, bLat: number, bLon: number): number {
  const dLat = toRad(bLat - aLat), dLon = toRad(bLon - aLon);
  const s = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(aLat)) * Math.cos(toRad(bLat)) * Math.sin(dLon / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(s));
}

// Spatial grid (~1.1 km cells) so "POIs near (lat,lon)" is a 3×3 cell lookup,
// not a scan of every POI. (Cell size > RADIUS_KM so the 3×3 neighbourhood is
// guaranteed to contain every POI within the radius.)
const CELL_DEG = 0.01; // ≈ 1.1 km near the equator
const cellKey = (lat: number, lon: number) => `${Math.floor(lat / CELL_DEG)}:${Math.floor(lon / CELL_DEG)}`;

export interface LifestyleIndex {
  grids: Record<string, Map<string, AmenityPoi[]>>; // one spatial grid per amenity type
}

export function buildLifestyleIndex(byType: Record<string, AmenityPoi[]>): LifestyleIndex {
  const grids: Record<string, Map<string, AmenityPoi[]>> = {};
  for (const type of LIFESTYLE_TYPES) {
    const g = new Map<string, AmenityPoi[]>();
    for (const p of byType[type] ?? []) {
      const k = cellKey(p.lat, p.lon);
      let bucket = g.get(k);
      if (!bucket) { bucket = []; g.set(k, bucket); }
      bucket.push(p);
    }
    grids[type] = g;
  }
  return { grids };
}

function countWithin(grid: Map<string, AmenityPoi[]>, lat: number, lon: number): number {
  const ci = Math.floor(lat / CELL_DEG), cj = Math.floor(lon / CELL_DEG);
  let n = 0;
  for (let di = -1; di <= 1; di++) {
    for (let dj = -1; dj <= 1; dj++) {
      const cell = grid.get(`${ci + di}:${cj + dj}`);
      if (!cell) continue;
      for (const p of cell) if (haversineKm(lat, lon, p.lat, p.lon) <= LIFESTYLE_RADIUS_KM) n++;
    }
  }
  return n;
}

/** 0–100 lifestyle score for a point, from nearby-amenity counts (see TWEAK). */
export function scoreLifestyle(index: LifestyleIndex, lat: number, lon: number): number {
  let acc = 0, wsum = 0;
  for (const type of LIFESTYLE_TYPES) {
    const { weight, enough } = LIFESTYLE_AMENITIES[type];
    const count = countWithin(index.grids[type], lat, lon);
    acc += weight * Math.min(count / enough, 1);
    wsum += weight;
  }
  return wsum > 0 ? Math.round((acc / wsum) * 100) : 0;
}
