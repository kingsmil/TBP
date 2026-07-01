import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { ArrowLeft, Landmark, Moon, Sun, Info, TrendingUp } from "lucide-react";
import { getPrivateTransactions } from "../lib/api";
import type { PrivateTransaction, PrivatePropertyType, PrivateSaleType } from "../types";
import PrivateProjectAutocomplete from "./PrivateProjectAutocomplete";

const TYPE_LABEL: Record<PrivatePropertyType, string> = {
  CONDO: "Condo", APARTMENT: "Apartment", EC: "Exec Condo", LANDED: "Landed", STRATA_LANDED: "Strata landed",
};
const SALE_LABEL: Record<PrivateSaleType, string> = {
  NEW_SALE: "New sale", RESALE: "Resale", SUB_SALE: "Sub sale",
};
const TYPES = Object.keys(TYPE_LABEL) as PrivatePropertyType[];
const SALES = Object.keys(SALE_LABEL) as PrivateSaleType[];

interface Props {
  onBack: () => void;
  theme: "light" | "dark";
  onToggleTheme: () => void;
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-2xl font-bold tabular-nums">{value}</div>
      {hint && <div className="text-[11px] text-muted-foreground">{hint}</div>}
    </div>
  );
}

const psf = (v: number | null | undefined) => (v != null ? `$${v.toLocaleString()}` : "—");

export default function PrivateDashboard({ onBack, theme, onToggleTheme }: Props) {
  const [project, setProject] = useState("");
  const [search, setSearch] = useState("");
  const [propertyType, setPropertyType] = useState("");
  const [saleType, setSaleType] = useState("");

  const filters = { project: project || undefined, property_type: propertyType || undefined, sale_type: saleType || undefined };
  const q = useQuery({
    queryKey: ["private-txns", filters],
    queryFn: () => getPrivateTransactions(filters),
    staleTime: 6e5,
  });

  const data = q.data;
  const rows = data?.results ?? [];
  const s = data?.summary;
  const trendData = useMemo(
    () => (data?.trend ?? []).map((t) => ({ month: t.month.slice(2), psf: t.median_psf })),
    [data?.trend],
  );

  return (
    <div className="flex h-full flex-col bg-background">
      <header className="flex items-center justify-between gap-3 border-b border-border bg-card px-5 py-3">
        <div className="flex items-center gap-3">
          <button type="button" onClick={onBack}
            className="flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium hover:bg-muted">
            <ArrowLeft className="h-3.5 w-3.5" /> Change
          </button>
          <div className="flex items-center gap-2">
            <Landmark className="h-4 w-4 text-primary" />
            <div>
              <h1 className="text-base font-bold leading-tight">Private Property</h1>
              <p className="text-xs text-muted-foreground">Condo · apartment · EC · landed — URA transactions</p>
            </div>
          </div>
        </div>
        <button type="button" onClick={onToggleTheme} title="Toggle theme"
          className="flex h-8 w-8 items-center justify-center rounded-md border border-border hover:bg-muted">
          {theme === "light" ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
        </button>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto p-5">
        <div className="mx-auto max-w-5xl space-y-5">
          {/* Caveat */}
          <div className="flex items-start gap-2 rounded-xl border border-border bg-muted/40 p-3 text-xs text-muted-foreground">
            <Info className="mt-0.5 h-4 w-4 shrink-0" />
            <p>
              Source: <strong>URA</strong> caveats (private residential, ~last 60 months). Some resale/sub-sale
              deals may be missing — lodging a caveat isn&apos;t mandatory.
              {data?.mock && " Showing sample data (no URA credentials configured)."}
            </p>
          </div>

          {/* Filters */}
          <div className="flex flex-wrap items-end gap-2">
            <form
              onSubmit={(e) => { e.preventDefault(); setProject(search.trim()); }}
              className="w-64">
              <PrivateProjectAutocomplete
                compact
                value={search}
                onChange={(v) => {
                  const next = v ?? "";
                  setSearch(next);
                  setProject(next.trim());
                }}
              />
            </form>
            <label className="flex flex-col gap-1">
              <span className="text-[10px] font-medium text-muted-foreground">Property type</span>
              <select value={propertyType} onChange={(e) => setPropertyType(e.target.value)}
                className="h-8 rounded-md border border-input bg-background px-2 text-xs">
                <option value="">All types</option>
                {TYPES.map((t) => <option key={t} value={t}>{TYPE_LABEL[t]}</option>)}
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-[10px] font-medium text-muted-foreground">Sale type</span>
              <select value={saleType} onChange={(e) => setSaleType(e.target.value)}
                className="h-8 rounded-md border border-input bg-background px-2 text-xs">
                <option value="">All sales</option>
                {SALES.map((t) => <option key={t} value={t}>{SALE_LABEL[t]}</option>)}
              </select>
            </label>
            {(project || propertyType || saleType) && (
              <button type="button"
                onClick={() => { setProject(""); setSearch(""); setPropertyType(""); setSaleType(""); }}
                className="h-8 rounded-md border border-border px-2.5 text-xs font-medium hover:bg-muted">
                Clear
              </button>
            )}
          </div>

          {q.isLoading && <div className="p-6 text-center text-sm text-muted-foreground">Loading transactions…</div>}
          {q.isError && (
            <div className="rounded-md border border-dashed border-border bg-muted/40 p-4 text-sm text-muted-foreground">
              Couldn&apos;t load private transactions. Please try again.
            </div>
          )}

          {data && (
            <>
              {/* Stats */}
              <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
                <Stat label="Transactions" value={s ? s.count.toLocaleString() : "—"} />
                <Stat label="Median PSF" value={psf(s?.median_psf)} />
                <Stat label="Average PSF" value={psf(s?.avg_psf)} />
                <Stat label="Lowest PSF" value={psf(s?.min_psf)} />
                <Stat label="Highest PSF" value={psf(s?.max_psf)} />
              </div>

              {data.latest && (
                <div className="rounded-xl border border-border bg-card p-3 text-xs text-muted-foreground">
                  Latest: <span className="font-medium text-foreground">{data.latest.project_name ?? data.latest.address}</span>{" "}
                  · {TYPE_LABEL[data.latest.property_type]} · {SALE_LABEL[data.latest.sale_type]} ·{" "}
                  ${data.latest.price.toLocaleString()} · {psf(data.latest.psf)} psf · {data.latest.sale_date.slice(0, 7)}
                </div>
              )}

              {/* Trend */}
              {trendData.length > 1 && (
                <div className="rounded-xl border border-border bg-card p-4">
                  <h2 className="mb-3 flex items-center gap-1.5 text-sm font-semibold">
                    <TrendingUp className="h-4 w-4" /> Median PSF by month
                  </h2>
                  <div className="h-52">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={trendData} margin={{ top: 5, right: 10, left: 5, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                        <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                        <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `$${v}`} width={52} />
                        <Tooltip formatter={(v: number) => [`$${v.toLocaleString()}`, "Median PSF"]} />
                        <Line type="monotone" dataKey="psf" stroke="hsl(var(--primary))" strokeWidth={2} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}

              {/* Transactions table */}
              {rows.length === 0 ? (
                <div className="rounded-md border border-dashed border-border bg-muted/40 p-8 text-center text-sm text-muted-foreground">
                  No transactions match these filters.
                </div>
              ) : (
                <div className="overflow-x-auto rounded-xl border border-border bg-card">
                  <table className="w-full border-collapse text-xs">
                    <thead>
                      <tr className="border-b border-border text-left text-muted-foreground">
                        <th className="py-2 pl-3 pr-2 font-medium">Project</th>
                        <th className="py-2 pr-2 font-medium">Type</th>
                        <th className="py-2 pr-2 font-medium">Sale</th>
                        <th className="py-2 pr-2 font-medium">Dist</th>
                        <th className="py-2 pr-2 text-right font-medium">Price</th>
                        <th className="py-2 pr-2 text-right font-medium">Area</th>
                        <th className="py-2 pr-2 text-right font-medium">PSF</th>
                        <th className="py-2 pr-2 font-medium">Floor</th>
                        <th className="py-2 pr-3 font-medium">Date</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((r: PrivateTransaction) => (
                        <tr key={r.id} className="border-b border-border/50">
                          <td className="py-2 pl-3 pr-2 font-medium">
                            {r.project_name ?? r.address ?? "—"}
                            {r.tenure && <span className="ml-1 text-[10px] text-muted-foreground">· {r.tenure.includes("Freehold") ? "FH" : "LH"}</span>}
                          </td>
                          <td className="py-2 pr-2">{TYPE_LABEL[r.property_type]}</td>
                          <td className="py-2 pr-2 text-muted-foreground">{SALE_LABEL[r.sale_type]}</td>
                          <td className="py-2 pr-2 text-muted-foreground">{r.district ?? "—"}</td>
                          <td className="py-2 pr-2 text-right tabular-nums">${r.price.toLocaleString()}</td>
                          <td className="py-2 pr-2 text-right tabular-nums text-muted-foreground">{r.area_sqft ? `${r.area_sqft} sf` : "—"}</td>
                          <td className="py-2 pr-2 text-right font-semibold tabular-nums">{psf(r.psf)}</td>
                          <td className="py-2 pr-2 text-muted-foreground">{r.floor_range ?? "—"}</td>
                          <td className="py-2 pr-3 tabular-nums">{r.sale_date.slice(0, 7)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <p className="text-[10px] text-muted-foreground">
                Showing {rows.length} of {s?.count ?? 0} matching transactions. Not affiliated with URA.
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
