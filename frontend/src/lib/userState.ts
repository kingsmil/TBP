/**
 * Saved user state with graceful anonymous fallback (Feature 1).
 *
 * - Logged-in (real token) or dev-bypass user  -> persist to the server.
 * - Anonymous user                             -> keep state in localStorage,
 *   and offer to push it to the server on login.
 *
 * This keeps browsing/search open to everyone; only *permanent* saving needs
 * auth, exactly mirroring the backend `require_user` gating.
 */
import {
  getMyPreferences, putMyPreferences,
  getMyLocations, createMyLocation, updateMyLocation, deleteMyLocation,
} from "./api";
import { getToken, devAuthEnabled } from "./auth";
import type { SavedLocation, UserPreferences } from "../types";

const LS_PREFS = "hdb_local_prefs";
const LS_LOCS = "hdb_local_locations";

export type AuthState = "anonymous" | "logged-in" | "dev";

export function authState(): AuthState {
  if (getToken()) return "logged-in";
  if (devAuthEnabled()) return "dev";
  return "anonymous";
}

/** Whether saved state will be persisted server-side (vs local-only). */
export function canPersist(): boolean {
  return authState() !== "anonymous";
}

// ── local (anonymous) store ───────────────────────────────────────────────────

function readLocal<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

export function hasPendingLocalState(): boolean {
  const prefs = readLocal<UserPreferences>(LS_PREFS, {});
  const locs = readLocal<SavedLocation[]>(LS_LOCS, []);
  return Object.keys(prefs).length > 0 || locs.length > 0;
}

export function clearLocalState(): void {
  localStorage.removeItem(LS_PREFS);
  localStorage.removeItem(LS_LOCS);
}

// ── preferences ───────────────────────────────────────────────────────────────

export async function loadPreferences(): Promise<UserPreferences> {
  if (canPersist()) {
    try {
      return await getMyPreferences();
    } catch {
      return readLocal<UserPreferences>(LS_PREFS, {});
    }
  }
  return readLocal<UserPreferences>(LS_PREFS, {});
}

export async function savePreferences(prefs: UserPreferences): Promise<UserPreferences> {
  if (canPersist()) {
    return putMyPreferences(prefs);
  }
  const merged = { ...readLocal<UserPreferences>(LS_PREFS, {}), ...prefs };
  localStorage.setItem(LS_PREFS, JSON.stringify(merged));
  return merged;
}

// ── locations ─────────────────────────────────────────────────────────────────

export async function loadLocations(): Promise<SavedLocation[]> {
  if (canPersist()) {
    try {
      return (await getMyLocations()).results;
    } catch {
      return readLocal<SavedLocation[]>(LS_LOCS, []);
    }
  }
  return readLocal<SavedLocation[]>(LS_LOCS, []);
}

export async function addLocation(loc: Omit<SavedLocation, "id">): Promise<SavedLocation> {
  if (canPersist()) return createMyLocation(loc);
  const locs = readLocal<SavedLocation[]>(LS_LOCS, []);
  const created = { ...loc, id: Date.now() } as SavedLocation; // local temp id
  locs.push(created);
  localStorage.setItem(LS_LOCS, JSON.stringify(locs));
  return created;
}

export async function editLocation(id: number, patch: Partial<SavedLocation>): Promise<SavedLocation> {
  if (canPersist()) return updateMyLocation(id, patch);
  const locs = readLocal<SavedLocation[]>(LS_LOCS, []);
  const idx = locs.findIndex((l) => l.id === id);
  if (idx >= 0) {
    locs[idx] = { ...locs[idx], ...patch };
    localStorage.setItem(LS_LOCS, JSON.stringify(locs));
    return locs[idx];
  }
  throw new Error("location not found");
}

export async function removeLocation(id: number): Promise<void> {
  if (canPersist()) {
    await deleteMyLocation(id);
    return;
  }
  const locs = readLocal<SavedLocation[]>(LS_LOCS, []).filter((l) => l.id !== id);
  localStorage.setItem(LS_LOCS, JSON.stringify(locs));
}

// ── push local -> server after login ──────────────────────────────────────────

/**
 * Migrate anonymous local state into the freshly-logged-in account, then clear
 * it. Preferences are merged; each local location is created server-side.
 * Safe to call when there's nothing pending.
 */
export async function pushLocalStateToServer(): Promise<void> {
  if (!canPersist()) return;
  const prefs = readLocal<UserPreferences>(LS_PREFS, {});
  const locs = readLocal<SavedLocation[]>(LS_LOCS, []);
  if (Object.keys(prefs).length > 0) {
    try { await putMyPreferences(prefs); } catch { /* keep local on failure */ return; }
  }
  for (const l of locs) {
    const { id: _id, created_at: _c, updated_at: _u, ...rest } = l;
    try { await createMyLocation(rest as Omit<SavedLocation, "id">); } catch { /* skip dupes */ }
  }
  clearLocalState();
}
