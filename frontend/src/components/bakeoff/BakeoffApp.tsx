import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import "./bakeoff.css";
import { X } from "lucide-react";
import type { SearchFilters } from "../../types";
import { MAP_SEARCH_LIMIT } from "../../lib/mapConfig";
import { getStoredUser, clearAuth, type AuthUser } from "../../lib/auth";
import { getMyPreferences, putMyPreferences } from "../../lib/api";
import { loadLocations, authState } from "../../lib/userState";
import AuthModal from "../AuthModal";
import SavedPlacesPanel from "../SavedPlacesPanel";
import BtoDashboard from "../BtoDashboard";
import RecommendWizard from "../RecommendWizard";
import InsightsModal from "./InsightsModal";
import SavedHomesPanel, { type SavedSnapshot } from "./SavedHomesPanel";
import Onboarding from "./Onboarding";
import type { CardItem, Mode, Weights } from "./types";
import { DEFAULT_WEIGHTS, migrateWeights } from "./types";
import { useListings, type Place } from "./useListings";

function useDebounced<T>(value: T, ms: number): T {
  const [d, setD] = useState(value);
  useEffect(() => { const t = setTimeout(() => setD(value), ms); return () => clearTimeout(t); }, [value, ms]);
  return d;
}

// List sort comparators (nulls sink to the bottom).
const SORT_CMP: Record<string, (a: CardItem, b: CardItem) => number> = {
  match: (a, b) => (b.score ?? -1) - (a.score ?? -1),
  "price-asc": (a, b) => (a.price ?? Infinity) - (b.price ?? Infinity),
  "price-desc": (a, b) => (b.price ?? -Infinity) - (a.price ?? -Infinity),
  "psf-asc": (a, b) => (a.psf ?? Infinity) - (b.psf ?? Infinity),
  "psf-desc": (a, b) => (b.psf ?? -Infinity) - (a.psf ?? -Infinity),
  newest: (a, b) => (b.sortDate ?? -Infinity) - (a.sortDate ?? -Infinity),
  "area-desc": (a, b) => (b.area ?? -Infinity) - (a.area ?? -Infinity),
  appreciation: (a, b) => (b.appreciation ?? -Infinity) - (a.appreciation ?? -Infinity),
};
import { useIsDesktop } from "./useMediaQuery";
import { type ShellProps, CompareBar, sortOptionsFor } from "./shell";
import LayoutFloatingGlass from "./LayoutFloatingGlass";
import CompareView from "./CompareView";

function loadSet(key: string): Set<string> {
  try {
    const raw = localStorage.getItem(key);
    return new Set(raw ? (JSON.parse(raw) as string[]) : []);
  } catch { return new Set(); }
}
function saveSet(key: string, set: Set<string>) {
  try { localStorage.setItem(key, JSON.stringify([...set])); } catch { /* ignore */ }
}

/** Build a saved-home snapshot from a loaded card. */
function snapOf(it: CardItem): SavedSnapshot {
  return {
    id: it.id, mode: it.mode, title: it.title, subtitle: it.subtitle,
    price: it.price ?? null, priceLabel: it.priceLabel ?? "", psf: it.psf ?? null,
    score: it.score ?? null, lat: it.lat ?? null, lon: it.lon ?? null,
    blockId: it.block?.block_id,
  };
}
/** Minimal stand-in for a saved id whose card isn't loaded yet (e.g. synced from
 *  the account) — so the favourites list + count never disagree. */
function placeholderSnap(id: string): SavedSnapshot {
  const mode: Mode = id.startsWith("p-") ? "private" : id.startsWith("b-") ? "bto" : "resale";
  return { id, mode, title: "Saved home", subtitle: "Open to locate", price: null, priceLabel: "", psf: null, score: null, lat: null, lon: null };
}

/** The "Floating Glass" redesign shell (full-screen map + floating UI). Owns
 *  shared state + live data. Mounted opt-in (?ui=on) while it's built out. */
export default function BakeoffApp() {
  const [modes, setModes] = useState<Mode[]>(["resale"]);
  const [combine, setCombineState] = useState(false);
  const [filters, setFilters] = useState<SearchFilters>({ limit: MAP_SEARCH_LIMIT });
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [savedIds, setSavedIds] = useState<Set<string>>(() => loadSet("hdb_saved"));
  const [compareIds, setCompareIds] = useState<Set<string>>(() => loadSet("hdb_compare"));
  // Persisted display snapshots of saved homes, so the favourites list works even
  // before/without the live cards being loaded (other modes, fresh reload).
  const [savedSnaps, setSavedSnaps] = useState<Record<string, SavedSnapshot>>(() => {
    try { return JSON.parse(localStorage.getItem("hdb_saved_snap") || "{}"); } catch { return {}; }
  });
  useEffect(() => { try { localStorage.setItem("hdb_saved_snap", JSON.stringify(savedSnaps)); } catch { /* ignore */ } }, [savedSnaps]);
  const [weights, setWeights] = useState<Weights>(() => {
    try { const raw = localStorage.getItem("hdb_weights"); return raw ? { ...DEFAULT_WEIGHTS, ...migrateWeights(JSON.parse(raw)) } : DEFAULT_WEIGHTS; } catch { return DEFAULT_WEIGHTS; }
  });
  const [colorByScore, setColorByScore] = useState<boolean>(() => localStorage.getItem("hdb_colorByScore") === "1");
  useEffect(() => { try { localStorage.setItem("hdb_weights", JSON.stringify(weights)); } catch { /* ignore */ } }, [weights]);
  useEffect(() => { try { localStorage.setItem("hdb_colorByScore", colorByScore ? "1" : "0"); } catch { /* ignore */ } }, [colorByScore]);

  // First-run intake: shown once per brand-new user (anon → localStorage flag;
  // logged-in → synced via account metadata), then never again.
  const [onboarded, setOnboarded] = useState<boolean>(() => localStorage.getItem("hdb_onboarded") === "1");
  const finishOnboarding = () => { setOnboarded(true); try { localStorage.setItem("hdb_onboarded", "1"); } catch { /* ignore */ } };

  // Persist saved + compare locally so they survive reloads (anon cache).
  useEffect(() => saveSet("hdb_saved", savedIds), [savedIds]);
  useEffect(() => saveSet("hdb_compare", compareIds), [compareIds]);

  // ── Auth + account-synced shortlist ───────────────────────────────────────
  const [authUser, setAuthUser] = useState<AuthUser | null>(() => getStoredUser());
  const [showAuth, setShowAuth] = useState(false);
  const synced = useRef(false);

  // On login: merge the account's saved/compare (stored in preferences metadata)
  // with whatever was saved anonymously, so nothing is lost.
  useEffect(() => {
    if (!authUser) { synced.current = false; return; }
    let cancelled = false;
    getMyPreferences()
      .then((prefs) => {
        if (cancelled) return;
        const meta = (prefs?.metadata_json ?? {}) as { saved?: string[]; compare?: string[]; weights?: Weights; onboarded?: boolean; snaps?: Record<string, SavedSnapshot> };
        if (meta.snaps) setSavedSnaps((prev) => ({ ...meta.snaps, ...prev }));
        if (meta.saved?.length) setSavedIds((prev) => new Set([...prev, ...meta.saved!]));
        if (meta.compare?.length) setCompareIds((prev) => new Set([...prev, ...meta.compare!]));
        if (meta.weights) setWeights((w) => ({ ...w, ...migrateWeights(meta.weights!) }));
        // Returning account that's already onboarded → skip intake.
        if (meta.onboarded) finishOnboarding();
      })
      .catch(() => { /* not reachable / not authed — stay local */ })
      .finally(() => { if (!cancelled) synced.current = true; });
    return () => { cancelled = true; };
  }, [authUser]);

  // While logged in, push changes to the account (debounced).
  useEffect(() => {
    if (!authUser || !synced.current) return;
    const t = setTimeout(() => {
      putMyPreferences({ metadata_json: { saved: [...savedIds], compare: [...compareIds], weights, onboarded, snaps: savedSnaps } }).catch(() => {});
    }, 500);
    return () => clearTimeout(t);
  }, [savedIds, compareIds, weights, onboarded, savedSnaps, authUser]);

  const onAccount = () => {
    if (authUser) { clearAuth(); setAuthUser(null); }
    else setShowAuth(true);
  };

  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [filterOpen, setFilterOpen] = useState(false);
  const [showCompare, setShowCompare] = useState(false);
  const [showSaved, setShowSaved] = useState(false);
  const [showSavedHomes, setShowSavedHomes] = useState(false);
  const [showInsights, setShowInsights] = useState(false);
  const [showBto, setShowBto] = useState(false);
  const [showHelp, setShowHelp] = useState(false);

  // Theme (light/dark) — applies the same way the classic app does.
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    const s = localStorage.getItem("hdb-match-theme");
    if (s === "light" || s === "dark") return s;
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    document.documentElement.style.colorScheme = theme;
    try { localStorage.setItem("hdb-match-theme", theme); } catch { /* ignore */ }
  }, [theme]);
  const toggleTheme = () => setTheme((t) => (t === "light" ? "dark" : "light"));
  const isDesktop = useIsDesktop();

  // Single-tap = focused view; in Combine mode, tap toggles a mode in/out.
  const toggleMode = (m: Mode) => setModes((prev) => {
    if (!combine) return [m];
    if (prev.includes(m)) {
      const next = prev.filter((x) => x !== m);
      return next.length ? next : prev; // keep at least one active
    }
    return [...prev, m];
  });
  const setCombine = (on: boolean) => {
    setCombineState(on);
    if (!on) setModes((prev) => (prev.length > 1 ? [prev[0]] : prev)); // collapse to one
  };

  const [sort, setSort] = useState("match");
  const dWeights = useDebounced(weights, 200);
  // Saved places (home/work/school) → fed into the commute score so blocks are
  // ranked by proximity to where YOU need to be.
  const savedLocs = useQuery({ queryKey: ["saved-locations", authState()], queryFn: loadLocations });
  // Geocoded saved places (label + coords) — for the score AND the per-property
  // "how long to get there" panel.
  const savedPlaces = useMemo(
    () => (savedLocs.data ?? [])
      .filter((l) => l.lat != null && l.lng != null)
      .map((l) => ({ label: l.label, lat: l.lat as number, lon: l.lng as number })),
    [savedLocs.data],
  );
  const places = useMemo<Place[]>(() => savedPlaces.map((p) => ({ lat: p.lat, lon: p.lon })), [savedPlaces]);
  const { items: allItems, blocks, isLoading, isError } = useListings(modes, filters, dWeights, places);

  const items = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = q
      ? allItems.filter((it) => it.title.toLowerCase().includes(q) || it.subtitle.toLowerCase().includes(q))
      : allItems;
    const cmp = SORT_CMP[sort] ?? SORT_CMP.match;
    return [...filtered].sort(cmp);
  }, [allItems, query, sort]);

  // Keep the sort valid for the active mode(s) — reset to the first allowed one
  // when the current sort isn't offered (e.g. "match" while viewing BTO).
  useEffect(() => {
    const allowed = sortOptionsFor(modes).map((o) => o.value);
    if (!allowed.includes(sort)) setSort(allowed[0] ?? "newest");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modes]);

  // Cache every card we've loaded (by id) so compared items survive mode switches
  // / filtering — the compare view can still show them.
  const itemCache = useRef(new Map<string, CardItem>());
  useEffect(() => { for (const it of allItems) itemCache.current.set(it.id, it); }, [allItems]);
  const compareItems = useMemo(
    () => [...compareIds].map((id) => itemCache.current.get(id)).filter(Boolean) as CardItem[],
    [compareIds, allItems],
  );

  const toggle = (set: React.Dispatch<React.SetStateAction<Set<string>>>) => (id: string) =>
    set((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  // Favouriting requires an account — otherwise it's a "fake favourite" that only
  // lives on this device. Prompt sign-in instead of silently faking it.
  const toggleSave = (id: string) => {
    if (!authUser) { setShowAuth(true); return; }
    toggle(setSavedIds)(id);
    setSavedSnaps((prev) => {
      if (prev[id]) { const next = { ...prev }; delete next[id]; return next; }
      const it = itemCache.current.get(id);
      return it ? { ...prev, [id]: snapOf(it) } : prev;
    });
  };

  // Backfill snapshots for saved ids that don't have one yet (e.g. merged from the
  // account, or saved before the card loaded), so the list matches the count.
  useEffect(() => {
    setSavedSnaps((prev) => {
      let changed = false;
      const next = { ...prev };
      for (const id of savedIds) {
        if (!next[id]) { const it = itemCache.current.get(id); if (it) { next[id] = snapOf(it); changed = true; } }
      }
      return changed ? next : prev;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [savedIds, allItems]);

  // Every saved id renders — with its snapshot, or a placeholder until one loads —
  // so "N saved" and the Saved homes list can never disagree.
  const savedHomes = useMemo(
    () => [...savedIds].map((id) => savedSnaps[id] ?? placeholderSnap(id)),
    [savedIds, savedSnaps],
  );
  const openSavedHome = (id: string) => {
    const snap = savedSnaps[id];
    if (snap && !modes.includes(snap.mode)) setModes([snap.mode]);
    setSelectedId(id);
    setShowSavedHomes(false);
  };

  const props: ShellProps = {
    modes, toggleMode, combine, setCombine, filters, setFilters, query, setQuery,
    items, blocks, isLoading, isError,
    selectedId, setSelectedId,
    savedIds, toggleSave,
    compareIds, toggleCompare: toggle(setCompareIds),
    hoveredId, setHoveredId,
    filterOpen, setFilterOpen, isDesktop,
    authEmail: authUser?.email ?? null, onAccount, savedPlaces,
    sort, setSort,
    weights, setWeights, colorByScore, setColorByScore,
    onSaved: () => setShowSaved(true),
    onSavedHomes: () => setShowSavedHomes(true),
    onInsights: () => setShowInsights(true),
    onBtoData: () => setShowBto(true),
    onHelp: () => setShowHelp(true),
    theme, onToggleTheme: toggleTheme,
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <LayoutFloatingGlass {...props} />
      {!onboarded && (
        <Onboarding
          weights={weights} setWeights={setWeights}
          modes={modes} setModes={setModes}
          filters={filters} setFilters={setFilters}
          authEmail={authUser?.email ?? null}
          onSignIn={() => setShowAuth(true)}
          onFinish={finishOnboarding} />
      )}
      <CompareBar saved={savedIds.size} comparing={compareIds.size}
        onSaved={() => setShowSavedHomes(true)} onCompare={() => setShowCompare(true)} />
      {showCompare && (
        <CompareView items={compareItems}
          onRemove={(id) => toggle(setCompareIds)(id)}
          onClear={() => { setCompareIds(new Set()); setShowCompare(false); }}
          onClose={() => setShowCompare(false)} />
      )}
      {showAuth && (
        <AuthModal
          onSuccess={(u) => { setAuthUser(u); setShowAuth(false); }}
          onClose={() => setShowAuth(false)}
        />
      )}
      {showSaved && (
        <SavedPlacesPanel authUser={authUser}
          onClose={() => setShowSaved(false)}
          onSignIn={() => { setShowSaved(false); setShowAuth(true); }} />
      )}
      {showSavedHomes && (
        <SavedHomesPanel snaps={savedHomes}
          onSelect={openSavedHome}
          onRemove={toggleSave}
          onClose={() => setShowSavedHomes(false)} />
      )}
      {showInsights && (
        <InsightsModal onClose={() => setShowInsights(false)}
          onSelectBlock={(id) => {
            // Top areas are resale blocks — make sure resale is on so it loads.
            if (!modes.includes("resale")) setModes(["resale"]);
            setSelectedId(`r-${id}`);
            setShowInsights(false);
          }} />
      )}
      {showBto && (
        <div className="fixed inset-0 z-[2400]">
          <BtoDashboard onBack={() => setShowBto(false)} theme={theme} onToggleTheme={toggleTheme} />
        </div>
      )}
      {showHelp && (
        <div className="fixed inset-0 z-[2400] flex items-center justify-center bg-black/40 p-4" onClick={() => setShowHelp(false)}>
          <div className="bo-glass flex max-h-[88vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl p-5" onClick={(e) => e.stopPropagation()}>
            <div className="mb-3 flex items-center justify-between">
              <div>
                <h2 className="text-base font-bold">Help me decide</h2>
                <p className="text-xs text-muted-foreground">A few questions to suggest BTO or resale.</p>
              </div>
              <button type="button" onClick={() => setShowHelp(false)} className="rounded-md p-1 hover:bg-muted"><X className="h-4 w-4" /></button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto">
              <RecommendWizard onSelect={(product) => { setModes([product]); setShowHelp(false); }} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
