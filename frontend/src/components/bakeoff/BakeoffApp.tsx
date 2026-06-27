import { useEffect, useMemo, useRef, useState } from "react";
import "./bakeoff.css";
import { Undo2 } from "lucide-react";
import type { SearchFilters } from "../../types";
import { MAP_SEARCH_LIMIT } from "../../lib/mapConfig";
import { setRedesign } from "../../lib/uiVariant";
import { getStoredUser, clearAuth, type AuthUser } from "../../lib/auth";
import { getMyPreferences, putMyPreferences } from "../../lib/api";
import AuthModal from "../AuthModal";
import type { CardItem, Mode } from "./types";
import { useListings } from "./useListings";

// List sort comparators (nulls sink to the bottom).
const SORT_CMP: Record<string, (a: CardItem, b: CardItem) => number> = {
  match: (a, b) => (b.score ?? -1) - (a.score ?? -1),
  "price-asc": (a, b) => (a.price ?? Infinity) - (b.price ?? Infinity),
  "price-desc": (a, b) => (b.price ?? -Infinity) - (a.price ?? -Infinity),
  "psf-asc": (a, b) => (a.psf ?? Infinity) - (b.psf ?? Infinity),
  "psf-desc": (a, b) => (b.psf ?? -Infinity) - (a.psf ?? -Infinity),
};
import { useIsDesktop } from "./useMediaQuery";
import { type ShellProps, CompareBar } from "./shell";
import LayoutFloatingGlass from "./LayoutFloatingGlass";

function loadSet(key: string): Set<string> {
  try {
    const raw = localStorage.getItem(key);
    return new Set(raw ? (JSON.parse(raw) as string[]) : []);
  } catch { return new Set(); }
}
function saveSet(key: string, set: Set<string>) {
  try { localStorage.setItem(key, JSON.stringify([...set])); } catch { /* ignore */ }
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
        const meta = (prefs?.metadata_json ?? {}) as { saved?: string[]; compare?: string[] };
        if (meta.saved?.length) setSavedIds((prev) => new Set([...prev, ...meta.saved!]));
        if (meta.compare?.length) setCompareIds((prev) => new Set([...prev, ...meta.compare!]));
      })
      .catch(() => { /* not reachable / not authed — stay local */ })
      .finally(() => { if (!cancelled) synced.current = true; });
    return () => { cancelled = true; };
  }, [authUser]);

  // While logged in, push changes to the account (debounced).
  useEffect(() => {
    if (!authUser || !synced.current) return;
    const t = setTimeout(() => {
      putMyPreferences({ metadata_json: { saved: [...savedIds], compare: [...compareIds] } }).catch(() => {});
    }, 500);
    return () => clearTimeout(t);
  }, [savedIds, compareIds, authUser]);

  const onAccount = () => {
    if (authUser) { clearAuth(); setAuthUser(null); }
    else setShowAuth(true);
  };

  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [filterOpen, setFilterOpen] = useState(false);
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
  const { items: allItems, blocks, isLoading, isError } = useListings(modes, filters);

  const items = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = q
      ? allItems.filter((it) => it.title.toLowerCase().includes(q) || it.subtitle.toLowerCase().includes(q))
      : allItems;
    const cmp = SORT_CMP[sort] ?? SORT_CMP.match;
    return [...filtered].sort(cmp);
  }, [allItems, query, sort]);

  const toggle = (set: React.Dispatch<React.SetStateAction<Set<string>>>) => (id: string) =>
    set((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const props: ShellProps = {
    modes, toggleMode, combine, setCombine, filters, setFilters, query, setQuery,
    items, blocks, isLoading, isError,
    selectedId, setSelectedId,
    savedIds, toggleSave: toggle(setSavedIds),
    compareIds, toggleCompare: toggle(setCompareIds),
    hoveredId, setHoveredId,
    filterOpen, setFilterOpen, isDesktop,
    authEmail: authUser?.email ?? null, onAccount,
    sort, setSort,
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <LayoutFloatingGlass {...props} />
      <CompareBar saved={savedIds.size} comparing={compareIds.size} />
      {showAuth && (
        <AuthModal
          onSuccess={(u) => { setAuthUser(u); setShowAuth(false); }}
          onClose={() => setShowAuth(false)}
        />
      )}
      <button type="button" onClick={() => setRedesign(false)}
        title="Back to the classic app"
        className="bo-glass fixed bottom-4 right-4 z-[3000] flex items-center gap-2 rounded-full px-4 py-2.5 text-sm font-semibold sm:bottom-6 sm:right-6">
        <Undo2 className="h-4 w-4" /> Classic
      </button>
    </div>
  );
}
