import { useEffect } from "react";
import { X, SlidersHorizontal } from "lucide-react";
import type { SearchFilters } from "../../types";

const FLAT_TYPES = ["2 ROOM", "3 ROOM", "4 ROOM", "5 ROOM", "EXECUTIVE"];
const MRT_PRESETS = [
  { label: "5 min", m: 400 }, { label: "10 min", m: 800 }, { label: "15 min", m: 1200 },
];

interface Props {
  filters: SearchFilters;
  onChange: (f: SearchFilters) => void;
  /** When set, render as a slide-up sheet (mobile); otherwise inline (desktop rail). */
  asSheet?: boolean;
  open?: boolean;
  onClose?: () => void;
}

export default function FilterSheet({ filters, onChange, asSheet, open, onClose }: Props) {
  useEffect(() => {
    if (!asSheet) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose?.();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [asSheet, onClose]);

  const set = (patch: Partial<SearchFilters>) => onChange({ ...filters, ...patch });
  const active =
    (filters.flat_type ? 1 : 0) + (filters.max_psf ? 1 : 0) +
    (filters.max_mrt_distance_m ? 1 : 0) + (filters.min_schools_within_1km ? 1 : 0);

  const body = (
    <div className="space-y-5">
      {/* Flat type */}
      <div>
        <div className="mb-2 text-sm font-semibold">Flat type</div>
        <div className="flex flex-wrap gap-2">
          {FLAT_TYPES.map((t) => {
            const on = filters.flat_type === t;
            return (
              <button key={t} type="button"
                onClick={() => set({ flat_type: on ? undefined : t })}
                className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                  on ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card hover:bg-muted"
                }`}>
                {t}
              </button>
            );
          })}
        </div>
      </div>

      {/* Walk to MRT */}
      <div>
        <div className="mb-2 text-sm font-semibold">Walk to MRT</div>
        <div className="flex flex-wrap gap-2">
          {MRT_PRESETS.map((p) => {
            const on = filters.max_mrt_distance_m === p.m;
            return (
              <button key={p.m} type="button"
                onClick={() => set({ max_mrt_distance_m: on ? undefined : p.m })}
                className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                  on ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card hover:bg-muted"
                }`}>
                {p.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Max price (PSF) slider */}
      <div>
        <div className="mb-1 flex items-center justify-between">
          <span className="text-sm font-semibold">Max PSF</span>
          <span className="text-xs font-medium text-muted-foreground">
            {filters.max_psf ? `$${filters.max_psf}` : "Any"}
          </span>
        </div>
        <input
          type="range" min={300} max={1200} step={25}
          value={filters.max_psf ?? 1200}
          onChange={(e) => set({ max_psf: Number(e.target.value) >= 1200 ? undefined : Number(e.target.value) })}
          className="w-full accent-primary"
        />
        <div className="flex justify-between text-[10px] text-muted-foreground"><span>$300</span><span>$1200+</span></div>
      </div>

      {/* Schools nearby */}
      <label className="flex items-center justify-between">
        <span className="text-sm font-semibold">Schools within 1 km</span>
        <input type="checkbox"
          checked={!!filters.min_schools_within_1km}
          onChange={(e) => set({ min_schools_within_1km: e.target.checked ? 1 : undefined })}
          className="h-5 w-5 accent-primary" />
      </label>

      {active > 0 && (
        <button type="button"
          onClick={() => onChange({ limit: filters.limit })}
          className="text-xs font-medium text-muted-foreground underline-offset-2 hover:underline">
          Clear all filters
        </button>
      )}
    </div>
  );

  if (!asSheet) {
    return (
      <div className="rounded-2xl border border-border bg-card p-4">
        <div className="mb-4 flex items-center gap-2 text-sm font-bold">
          <SlidersHorizontal className="h-4 w-4" /> Filters
        </div>
        {body}
      </div>
    );
  }

  return (
    <div className={`fixed inset-0 z-[2000] ${open ? "" : "pointer-events-none"}`}>
      <div className={`absolute inset-0 bg-black/40 transition-opacity ${open ? "opacity-100" : "opacity-0"}`}
        onClick={onClose} />
      <div className={`bo-glass absolute inset-x-0 bottom-0 mx-auto max-h-[80vh] max-w-md overflow-y-auto rounded-t-2xl p-5 pb-8 transition-transform duration-300 ease-out sm:bottom-4 sm:rounded-2xl ${
        open ? "translate-y-0" : "translate-y-full"
      }`}>
        <div className="mx-auto mb-4 h-1 w-10 rounded-full bg-muted" />
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-bold">Filters</h2>
          <button type="button" onClick={onClose} className="rounded-md p-1 hover:bg-muted"><X className="h-5 w-5" /></button>
        </div>
        {body}
        <button type="button" onClick={onClose}
          className="mt-6 w-full rounded-xl bg-primary py-3 text-sm font-semibold text-primary-foreground">
          Show results
        </button>
      </div>
    </div>
  );
}
