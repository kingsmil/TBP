import { useEffect } from "react";
import { X, SlidersHorizontal } from "lucide-react";
import type { SearchFilters } from "../../types";
import type { Mode } from "./types";
import PrivateProjectAutocomplete from "../PrivateProjectAutocomplete";

const FLAT_TYPES = ["2 ROOM", "3 ROOM", "4 ROOM", "5 ROOM", "EXECUTIVE"];
const MRT_PRESETS = [
  { label: "5 min", m: 400 }, { label: "10 min", m: 800 }, { label: "15 min", m: 1200 },
];
const PRIVATE_TYPES: [string, string][] = [
  ["CONDO", "Condo"], ["APARTMENT", "Apartment"], ["EC", "EC"],
  ["LANDED", "Landed"], ["STRATA_LANDED", "Strata landed"],
];
const PRIVATE_SALE_TYPES: [string, string][] = [
  ["NEW_SALE", "New sale"], ["RESALE", "Resale"], ["SUB_SALE", "Sub-sale"],
];
const PRIVATE_REGIONS: [string, string][] = [["CCR", "CCR"], ["RCR", "RCR"], ["OCR", "OCR"]];
const PRIVATE_TENURES: [string, string][] = [["freehold", "Freehold"], ["leasehold", "Leasehold"]];
const PRIVATE_FLOORS = [
  "01-05", "06-10", "11-15", "16-20", "21-25", "26-30", "31-35",
  "36-40", "41-45", "46-50", "51-55", "56-60", "61-65", "66-70",
];

interface Props {
  filters: SearchFilters;
  onChange: (f: SearchFilters) => void;
  modes: Mode[];
  /** When set, render as a slide-up sheet (mobile); otherwise inline (desktop rail). */
  asSheet?: boolean;
  open?: boolean;
  onClose?: () => void;
}

function Chip({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" onClick={onClick}
      className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
        on ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card hover:bg-muted"
      }`}>
      {children}
    </button>
  );
}

function PriceField({ filters, set }: { filters: SearchFilters; set: (p: Partial<SearchFilters>) => void }) {
  return (
    <div>
      <div className="mb-2 text-sm font-semibold">Max price</div>
      <div className="flex items-center gap-2 rounded-xl border border-border bg-card px-3">
        <span className="text-sm text-muted-foreground">$</span>
        <input type="number" inputMode="numeric" placeholder="Any"
          value={filters.max_price ?? ""}
          onChange={(e) => set({ max_price: e.target.value ? Number(e.target.value) : undefined })}
          className="h-10 flex-1 bg-transparent text-sm outline-none" />
      </div>
    </div>
  );
}

function TextField({
  label, value, placeholder, onChange,
}: {
  label: string;
  value?: string;
  placeholder?: string;
  onChange: (v: string | undefined) => void;
}) {
  return (
    <label className="block">
      <div className="mb-2 text-sm font-semibold">{label}</div>
      <input type="text" placeholder={placeholder}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value || undefined)}
        className="h-10 w-full rounded-xl border border-border bg-card px-3 text-sm outline-none" />
    </label>
  );
}

function NumberField({
  label, value, placeholder, prefix, suffix, onChange,
}: {
  label: string;
  value?: number;
  placeholder?: string;
  prefix?: string;
  suffix?: string;
  onChange: (v: number | undefined) => void;
}) {
  return (
    <label className="block">
      <div className="mb-2 text-sm font-semibold">{label}</div>
      <div className="flex items-center gap-2 rounded-xl border border-border bg-card px-3">
        {prefix && <span className="text-sm text-muted-foreground">{prefix}</span>}
        <input type="number" inputMode="numeric" placeholder={placeholder ?? "Any"}
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value ? Number(e.target.value) : undefined)}
          className="h-10 min-w-0 flex-1 bg-transparent text-sm outline-none" />
        {suffix && <span className="text-xs text-muted-foreground">{suffix}</span>}
      </div>
    </label>
  );
}

function DateField({
  label, value, onChange,
}: {
  label: string;
  value?: string;
  onChange: (v: string | undefined) => void;
}) {
  return (
    <label className="block">
      <div className="mb-2 text-sm font-semibold">{label}</div>
      <input type="date"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value || undefined)}
        className="h-10 w-full rounded-xl border border-border bg-card px-3 text-sm outline-none" />
    </label>
  );
}

function SelectField({
  label, value, options, onChange,
}: {
  label: string;
  value?: string;
  options: string[];
  onChange: (v: string | undefined) => void;
}) {
  return (
    <label className="block">
      <div className="mb-2 text-sm font-semibold">{label}</div>
      <select value={value ?? ""} onChange={(e) => onChange(e.target.value || undefined)}
        className="h-10 w-full rounded-xl border border-border bg-card px-3 text-sm outline-none">
        <option value="">Any</option>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  );
}

function PsfField({ filters, set }: { filters: SearchFilters; set: (p: Partial<SearchFilters>) => void }) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <span className="text-sm font-semibold">Max PSF</span>
        <span className="text-xs font-medium text-muted-foreground">{filters.max_psf ? `$${filters.max_psf}` : "Any"}</span>
      </div>
      <input type="range" min={300} max={1200} step={25} value={filters.max_psf ?? 1200}
        onChange={(e) => set({ max_psf: Number(e.target.value) >= 1200 ? undefined : Number(e.target.value) })}
        className="w-full accent-primary" />
      <div className="flex justify-between text-[10px] text-muted-foreground"><span>$300</span><span>$1200+</span></div>
    </div>
  );
}

export default function FilterSheet({ filters, onChange, modes, asSheet, open, onClose }: Props) {
  useEffect(() => {
    if (!asSheet) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose?.();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [asSheet, onClose]);

  const set = (patch: Partial<SearchFilters>) => onChange({ ...filters, ...patch });
  const multi = modes.length > 1;
  const activeCount = (Object.keys(filters) as (keyof SearchFilters)[])
    .filter((k) => k !== "limit" && k !== "bbox" && filters[k] != null).length;

  const header = (label: string) => multi
    ? <div className="text-[11px] font-bold uppercase tracking-wide text-muted-foreground">{label}</div>
    : null;

  const body = (
    <div className="space-y-5">
      {modes.includes("resale") && (
        <div className="space-y-5">
          {header("Resale")}
          <div>
            <div className="mb-2 text-sm font-semibold">Flat type</div>
            <div className="flex flex-wrap gap-2">
              {FLAT_TYPES.map((t) => <Chip key={t} on={filters.flat_type === t} onClick={() => set({ flat_type: filters.flat_type === t ? undefined : t })}>{t}</Chip>)}
            </div>
          </div>
          <div>
            <div className="mb-2 text-sm font-semibold">Walk to MRT</div>
            <div className="flex flex-wrap gap-2">
              {MRT_PRESETS.map((p) => <Chip key={p.m} on={filters.max_mrt_distance_m === p.m} onClick={() => set({ max_mrt_distance_m: filters.max_mrt_distance_m === p.m ? undefined : p.m })}>{p.label}</Chip>)}
            </div>
          </div>
          <PriceField filters={filters} set={set} />
          <PsfField filters={filters} set={set} />
          <label className="flex items-center justify-between">
            <span className="text-sm font-semibold">Schools within 1 km</span>
            <input type="checkbox" checked={!!filters.min_schools_within_1km}
              onChange={(e) => set({ min_schools_within_1km: e.target.checked ? 1 : undefined })}
              className="h-5 w-5 accent-primary" />
          </label>
        </div>
      )}

      {modes.includes("private") && (
        <div className="space-y-5">
          {header("Private")}
          <div className="grid grid-cols-1 gap-3">
            <PrivateProjectAutocomplete value={filters.project} onChange={(v) => set({ project: v })} />
            <TextField label="Street or address" value={filters.address} placeholder="e.g. Thiam Siew Avenue" onChange={(v) => set({ address: v })} />
          </div>
          <div>
            <div className="mb-2 text-sm font-semibold">Property type</div>
            <div className="flex flex-wrap gap-2">
              {PRIVATE_TYPES.map(([v, label]) => <Chip key={v} on={filters.property_type === v} onClick={() => set({ property_type: filters.property_type === v ? undefined : v })}>{label}</Chip>)}
            </div>
          </div>
          <div>
            <div className="mb-2 text-sm font-semibold">Sale type</div>
            <div className="flex flex-wrap gap-2">
              {PRIVATE_SALE_TYPES.map(([v, label]) => <Chip key={v} on={filters.sale_type === v} onClick={() => set({ sale_type: filters.sale_type === v ? undefined : v })}>{label}</Chip>)}
            </div>
          </div>
          <div>
            <div className="mb-2 text-sm font-semibold">Region</div>
            <div className="flex flex-wrap gap-2">
              {PRIVATE_REGIONS.map(([v, label]) => <Chip key={v} on={filters.planning_region === v} onClick={() => set({ planning_region: filters.planning_region === v ? undefined : v })}>{label}</Chip>)}
            </div>
          </div>
          <div>
            <div className="mb-2 text-sm font-semibold">Tenure</div>
            <div className="flex flex-wrap gap-2">
              {PRIVATE_TENURES.map(([v, label]) => <Chip key={v} on={filters.tenure === v} onClick={() => set({ tenure: filters.tenure === v ? undefined : v })}>{label}</Chip>)}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <TextField label="District" value={filters.district} placeholder="09" onChange={(v) => set({ district: v })} />
            <SelectField label="Floor range" value={filters.floor_range} options={PRIVATE_FLOORS} onChange={(v) => set({ floor_range: v })} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <NumberField label="Min price" value={filters.min_price} prefix="$" onChange={(v) => set({ min_price: v })} />
            <NumberField label="Max price" value={filters.max_price} prefix="$" onChange={(v) => set({ max_price: v })} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <NumberField label="Min PSF" value={filters.min_psf} prefix="$" suffix="psf" onChange={(v) => set({ min_psf: v })} />
            <NumberField label="Max PSF" value={filters.max_psf} prefix="$" suffix="psf" onChange={(v) => set({ max_psf: v })} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <NumberField label="Min area" value={filters.min_area_sqft} suffix="sqft" onChange={(v) => set({ min_area_sqft: v })} />
            <NumberField label="Max area" value={filters.max_area_sqft} suffix="sqft" onChange={(v) => set({ max_area_sqft: v })} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <DateField label="Sold from" value={filters.date_from} onChange={(v) => set({ date_from: v })} />
            <DateField label="Sold to" value={filters.date_to} onChange={(v) => set({ date_to: v })} />
          </div>
        </div>
      )}

      {modes.includes("bto") && (
        <div className="space-y-5">
          {header("BTO")}
          <div>
            <div className="mb-2 text-sm font-semibold">Flat type</div>
            <div className="flex flex-wrap gap-2">
              {FLAT_TYPES.map((t) => <Chip key={t} on={filters.flat_type === t} onClick={() => set({ flat_type: filters.flat_type === t ? undefined : t })}>{t}</Chip>)}
            </div>
          </div>
          <div>
            <div className="mb-2 text-sm font-semibold">Town</div>
            <input type="text" placeholder="e.g. Tampines"
              value={filters.town ?? ""}
              onChange={(e) => set({ town: e.target.value || undefined })}
              className="h-10 w-full rounded-xl border border-border bg-card px-3 text-sm outline-none" />
          </div>
        </div>
      )}

      {activeCount > 0 && (
        <button type="button" onClick={() => onChange({ limit: filters.limit })}
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
