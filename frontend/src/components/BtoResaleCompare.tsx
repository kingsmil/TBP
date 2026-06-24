import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { Building2, KeyRound, Clock, Flame, TrendingUp } from "lucide-react";
import { getCompareOptions, getBtoResaleCompare } from "../lib/api";

interface Props {
  onSelect: (product: "resale" | "bto") => void;
}

const sgd = (n: number | null | undefined) =>
  n == null ? "—" : `$${Math.round(n).toLocaleString()}`;

export default function BtoResaleCompare({ onSelect }: Props) {
  const options = useQuery({ queryKey: ["compare-options"], queryFn: getCompareOptions, staleTime: 6e5 });
  const [town, setTown] = useState("");
  const [flatType, setFlatType] = useState("");

  // Default the selectors once options load.
  useEffect(() => {
    if (options.data && !town) {
      setTown(options.data.towns.includes("Punggol") ? "Punggol" : options.data.towns[0] ?? "");
      setFlatType(options.data.flat_types.includes("4-room") ? "4-room" : options.data.flat_types[0] ?? "");
    }
  }, [options.data, town]);

  const cmp = useQuery({
    queryKey: ["bto-resale-compare", town, flatType],
    queryFn: () => getBtoResaleCompare(town, flatType),
    enabled: !!town && !!flatType,
    staleTime: 6e5,
  });

  const d = cmp.data;
  const resaleDearer = (d?.gap.price_diff ?? 0) > 0;

  if (options.isError) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-muted/40 p-4 text-sm text-muted-foreground">
        Comparison needs live data — run the backend with PostGIS (BTO + resale ingested).
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Selectors */}
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs font-medium">
          <span className="mb-1 block text-muted-foreground">Town</span>
          <select value={town} onChange={(e) => setTown(e.target.value)}
            className="h-9 w-44 rounded-md border border-input bg-background px-2 text-sm">
            {(options.data?.towns ?? []).map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </label>
        <label className="text-xs font-medium">
          <span className="mb-1 block text-muted-foreground">Flat type</span>
          <select value={flatType} onChange={(e) => setFlatType(e.target.value)}
            className="h-9 w-36 rounded-md border border-input bg-background px-2 text-sm">
            {(options.data?.flat_types ?? []).map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </label>
      </div>

      {d && (
        <>
          {/* Headline gap */}
          {d.gap.price_diff != null && (
            <div className="rounded-xl border border-border bg-primary/5 p-4">
              <p className="text-sm">
                In <strong>{d.town}</strong>, a <strong>{d.flat_type}</strong> resale costs about{" "}
                <strong className={resaleDearer ? "text-red-600" : "text-emerald-600"}>
                  {sgd(Math.abs(d.gap.price_diff))} {resaleDearer ? "more" : "less"}
                </strong>{" "}
                than a new BTO ({d.gap.price_pct}%).
                {resaleDearer && d.gap.annual_saving ? (
                  <> Choosing BTO saves roughly <strong>{sgd(d.gap.annual_saving)}/year</strong> of the ~3–4 year wait.</>
                ) : null}
              </p>
            </div>
          )}

          {/* Two columns */}
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-border bg-card p-4">
              <div className="mb-2 flex items-center gap-2 font-semibold"><Building2 className="h-4 w-4 text-primary" /> New flat (BTO)</div>
              <div className="text-2xl font-bold">{sgd(d.bto.mid_price)}</div>
              <div className="text-xs text-muted-foreground">
                {d.bto.min_price && d.bto.max_price ? `${sgd(d.bto.min_price)}–${sgd(d.bto.max_price)}` : "price n/a"}
                {d.bto.latest_year ? ` · FY${d.bto.latest_year}` : ""}
              </div>
              <ul className="mt-3 space-y-1.5 text-xs">
                <li className="flex items-center gap-2"><Clock className="h-3.5 w-3.5 text-muted-foreground" /> Wait {d.bto.wait_years}</li>
                <li className="flex items-center gap-2"><Flame className="h-3.5 w-3.5 text-muted-foreground" /> Ballot {d.bto.app_rate != null ? `${d.bto.app_rate}× subscribed` : "varies by launch"}</li>
              </ul>
            </div>

            <div className="rounded-xl border border-border bg-card p-4">
              <div className="mb-2 flex items-center gap-2 font-semibold"><KeyRound className="h-4 w-4 text-primary" /> Resale flat</div>
              <div className="text-2xl font-bold">{sgd(d.resale.median_price)}</div>
              <div className="text-xs text-muted-foreground">
                median · {d.resale.median_psf ? `$${d.resale.median_psf}/sqft` : "psf n/a"} · {d.resale.txn_count.toLocaleString()} recent sales
              </div>
              <ul className="mt-3 space-y-1.5 text-xs">
                <li className="flex items-center gap-2"><Clock className="h-3.5 w-3.5 text-muted-foreground" /> {d.resale.wait_years}</li>
                <li className="flex items-center gap-2"><TrendingUp className="h-3.5 w-3.5 text-muted-foreground" /> Price growth {d.resale.cagr_pct != null ? `${d.resale.cagr_pct}%/yr` : "n/a"}</li>
              </ul>
            </div>
          </div>

          {/* Price overlay */}
          {d.price_series.length > 1 && (
            <div className="rounded-xl border border-border bg-card p-4">
              <h3 className="mb-2 text-sm font-semibold">Price over time — BTO vs resale</h3>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={d.price_series} margin={{ top: 5, right: 10, left: 5, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                    <XAxis dataKey="year" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `$${Math.round(v / 1000)}k`} width={48} />
                    <Tooltip formatter={(v: number) => sgd(v)} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Line type="monotone" dataKey="bto" name="BTO" stroke="#0ea5e9" strokeWidth={2} dot={false} connectNulls />
                    <Line type="monotone" dataKey="resale" name="Resale" stroke="#f59e0b" strokeWidth={2} dot={false} connectNulls />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* CTAs */}
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={() => onSelect("bto")}
              className="flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90">
              <Building2 className="h-4 w-4" /> Explore BTO
            </button>
            <button type="button" onClick={() => onSelect("resale")}
              className="flex items-center gap-1.5 rounded-lg border border-border px-4 py-2 text-sm font-semibold hover:bg-muted">
              <KeyRound className="h-4 w-4" /> Explore Resale
            </button>
          </div>
          <p className="text-[10px] text-muted-foreground">
            BTO price: HDB offered range (data.gov.sg). Resale: median of recent transactions. Indicative — not advice.
          </p>
        </>
      )}
    </div>
  );
}
