import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CalendarClock, Info } from "lucide-react";
import { getBtoResaleSupply } from "../lib/api";
import type { BtoResaleSupplyFilters, BtoResaleSupplyRow } from "../types";

const CONF_STYLE: Record<string, string> = {
  HIGH: "bg-emerald-100 text-emerald-800",
  MEDIUM: "bg-yellow-100 text-yellow-800",
  LOW: "bg-orange-100 text-orange-800",
};
const CLASS_LABEL: Record<string, string> = {
  STANDARD: "Standard", PLUS: "Plus", PRIME: "Prime", PLH: "Prime (PLH)",
  UNCLASSIFIED: "Unclassified", UNKNOWN: "Unknown",
};
const SORT_LABEL: Record<string, string> = {
  soonest: "Soonest resale eligibility",
  town: "Town A–Z",
  completion: "Completion year",
  confidence: "Confidence level",
};

const FLAT_TYPES = ["2 ROOM", "3 ROOM", "4 ROOM", "5 ROOM"];

function fmtDate(iso: string | null, monthKnownHint = true): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  // Year-only estimates land on 1 Jan — show just the year to avoid false precision.
  if (!monthKnownHint || (d.getMonth() === 0 && d.getDate() === 1)) return String(d.getFullYear());
  return d.toLocaleDateString("en-SG", { year: "numeric", month: "short" });
}

export default function BtoResaleSupply() {
  const [filters, setFilters] = useState<BtoResaleSupplyFilters>({ sort: "soonest" });
  const q = useQuery({
    queryKey: ["bto-resale-supply", filters],
    queryFn: () => getBtoResaleSupply(filters),
    staleTime: 6e5,
  });

  const set = (patch: Partial<BtoResaleSupplyFilters>) =>
    setFilters((f) => ({ ...f, ...patch }));

  const data = q.data;
  const rows = data?.results ?? [];
  const facets = data?.facets;
  const empty = !q.isLoading && !q.isError && rows.length === 0;

  return (
    <div className="space-y-4">
      {/* Estimate warning */}
      <div className="flex items-start gap-2 rounded-xl border border-amber-300/60 bg-amber-50 p-3 text-xs text-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
        <p>
          These dates are <strong>estimates</strong> based on available completion/project data and
          HDB MOP rules. Actual resale eligibility depends on each owner&apos;s legal completion date,
          physical occupation period, and HDB rules.
        </p>
      </div>

      {/* Filters + sort */}
      <div className="flex flex-wrap items-end gap-2">
        <Field label="Town">
          <select value={filters.town ?? ""} onChange={(e) => set({ town: e.target.value || undefined })}
            className="h-8 rounded-md border border-input bg-background px-2 text-xs">
            <option value="">All towns</option>
            {(facets?.towns ?? []).map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </Field>
        <Field label="Classification">
          <select value={filters.classification ?? ""} onChange={(e) => set({ classification: e.target.value || undefined })}
            className="h-8 rounded-md border border-input bg-background px-2 text-xs">
            <option value="">All</option>
            {(facets?.classifications ?? []).map((c) => <option key={c} value={c}>{CLASS_LABEL[c] ?? c}</option>)}
          </select>
        </Field>
        <Field label="Flat type">
          <select value={filters.flat_type ?? ""} onChange={(e) => set({ flat_type: e.target.value || undefined })}
            className="h-8 rounded-md border border-input bg-background px-2 text-xs">
            <option value="">All</option>
            {FLAT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </Field>
        <Field label="Eligible from (year)">
          <input type="number" min={2020} max={2060} placeholder="e.g. 2028"
            value={filters.earliest_year ?? ""}
            onChange={(e) => set({ earliest_year: e.target.value ? Number(e.target.value) : undefined })}
            className="h-8 w-24 rounded-md border border-input bg-background px-2 text-xs" />
        </Field>
        <Field label="Confidence">
          <select value={filters.confidence ?? ""} onChange={(e) => set({ confidence: e.target.value || undefined })}
            className="h-8 rounded-md border border-input bg-background px-2 text-xs">
            <option value="">Any</option>
            {(facets?.confidences ?? ["HIGH", "MEDIUM", "LOW"]).map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </Field>
        <Field label="Sort by">
          <select value={filters.sort ?? "soonest"} onChange={(e) => set({ sort: e.target.value })}
            className="h-8 rounded-md border border-input bg-background px-2 text-xs">
            {(facets?.sorts ?? Object.keys(SORT_LABEL)).map((s) => <option key={s} value={s}>{SORT_LABEL[s] ?? s}</option>)}
          </select>
        </Field>
      </div>

      {q.isError && (
        <div className="rounded-md border border-dashed border-border bg-muted/40 p-4 text-sm text-muted-foreground">
          No resale-availability estimates yet. Run{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">python -m app.data.bto_mop</code> on the server (needs PostGIS).
        </div>
      )}
      {q.isLoading && <div className="p-6 text-center text-sm text-muted-foreground">Loading estimates…</div>}
      {empty && (
        <div className="rounded-md border border-dashed border-border bg-muted/40 p-6 text-center text-sm text-muted-foreground">
          No projects match these filters.
        </div>
      )}

      {rows.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-border bg-card">
          <table className="w-full border-collapse text-xs">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th className="py-2 pl-3 pr-2 font-medium">Project / estate</th>
                <th className="py-2 pr-2 font-medium">Town</th>
                <th className="py-2 pr-2 font-medium">Flat types</th>
                <th className="py-2 pr-2 font-medium">Class</th>
                <th className="py-2 pr-2 font-medium">Est. completion / keys</th>
                <th className="py-2 pr-2 text-right font-medium">MOP</th>
                <th className="py-2 pr-2 font-medium">Est. resale eligible</th>
                <th className="py-2 pr-3 font-medium">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => <Row key={r.id} r={r} />)}
            </tbody>
          </table>
        </div>
      )}

      <p className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
        <Info className="h-3 w-3" />
        {data ? `${data.count} project(s).` : ""} Estimates combine a curated seed of known
        completion dates with HDB launch metadata. Official sources cited per row where available.
      </p>
    </div>
  );
}

function Row({ r }: { r: BtoResaleSupplyRow }) {
  const monthKnown = r.confidence === "HIGH";
  const anchor = r.estimated_key_collection_date ?? r.estimated_completion_date;
  return (
    <tr className="border-b border-border/50 align-top" title={r.confidence_reason ?? undefined}>
      <td className="py-2 pl-3 pr-2 font-medium">
        {r.source_url ? (
          <a href={r.source_url} target="_blank" rel="noreferrer" className="hover:underline">{r.project_name}</a>
        ) : r.project_name}
        {r.launch_exercise && <span className="ml-1 text-[10px] text-muted-foreground">· {r.launch_exercise}</span>}
      </td>
      <td className="py-2 pr-2 text-muted-foreground">{r.town ?? "—"}</td>
      <td className="py-2 pr-2 text-muted-foreground">{r.flat_types ?? "—"}</td>
      <td className="py-2 pr-2">{CLASS_LABEL[r.flat_classification] ?? r.flat_classification}</td>
      <td className="py-2 pr-2 tabular-nums">{fmtDate(anchor, monthKnown)}</td>
      <td className="py-2 pr-2 text-right tabular-nums">{r.mop_years}y</td>
      <td className="py-2 pr-2 font-semibold tabular-nums">
        <span className="inline-flex items-center gap-1">
          <CalendarClock className="h-3 w-3 text-muted-foreground" />
          {fmtDate(r.estimated_resale_eligible_date, monthKnown)}
        </span>
      </td>
      <td className="py-2 pr-3">
        <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${CONF_STYLE[r.confidence] ?? ""}`}>
          {r.confidence}
        </span>
      </td>
    </tr>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10px] font-medium text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}
