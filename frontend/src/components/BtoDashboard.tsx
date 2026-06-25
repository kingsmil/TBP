import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { ArrowLeft, Building2, Users, Layers, Flame, Moon, Sun } from "lucide-react";
import { getBtoExercises, getBtoTrends, getBtoExercise, getBtoPriceTrends } from "../lib/api";
import type { BtoRate } from "../types";
import BtoResaleSupply from "./BtoResaleSupply";

const ROOM_COLORS: Record<string, string> = {
  "2-room": "#0ea5e9", "3-room": "#22c55e", "4-room": "#f59e0b", "5-room": "#ef4444",
};

interface Props {
  onBack: () => void;
  theme: "light" | "dark";
  onToggleTheme: () => void;
}

function rateColor(v: number | null): string {
  if (v == null) return "bg-muted text-muted-foreground";
  if (v <= 1) return "bg-emerald-100 text-emerald-800";
  if (v <= 3) return "bg-yellow-100 text-yellow-800";
  if (v <= 5) return "bg-orange-100 text-orange-800";
  return "bg-red-100 text-red-800";
}

function Stat({ icon: Icon, label, value, hint }: {
  icon: typeof Building2; label: string; value: string; hint?: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Icon className="h-4 w-4" /> {label}
      </div>
      <div className="mt-1 text-2xl font-bold tabular-nums">{value}</div>
      {hint && <div className="text-[11px] text-muted-foreground">{hint}</div>}
    </div>
  );
}

export default function BtoDashboard({ onBack, theme, onToggleTheme }: Props) {
  const exercises = useQuery({ queryKey: ["bto-exercises"], queryFn: getBtoExercises, staleTime: 6e5 });
  const trends = useQuery({ queryKey: ["bto-trends"], queryFn: getBtoTrends, staleTime: 6e5 });
  const [priceTown, setPriceTown] = useState<string>("");
  const priceTrends = useQuery({
    queryKey: ["bto-price-trends", priceTown],
    queryFn: () => getBtoPriceTrends(priceTown || undefined),
    staleTime: 6e5,
  });

  const [tab, setTab] = useState<"exercises" | "supply">("exercises");
  const list = exercises.data?.results ?? [];
  const [selected, setSelected] = useState<string | null>(null);
  const activeId = selected ?? list[0]?.exercise_id ?? null;

  const detail = useQuery({
    queryKey: ["bto-exercise", activeId],
    queryFn: () => getBtoExercise(activeId as string),
    enabled: !!activeId,
    staleTime: 6e5,
  });

  const ex = detail.data?.exercise;
  const chartData = useMemo(
    () => (trends.data?.overall ?? []).map((o) => ({ name: o.label.replace(" 20", " '"), rate: o.overall_app_rate ?? 0 })),
    [trends.data],
  );
  const priceData = useMemo(() => {
    const pt = priceTrends.data;
    if (!pt) return [];
    return pt.years.map((y) => {
      const row: Record<string, number | null> = { year: y };
      for (const rt of pt.by_room_type) {
        row[rt.room_type] = rt.series.find((s) => s.financial_year === y)?.mid ?? null;
      }
      return row;
    });
  }, [priceTrends.data]);
  const priceRoomTypes = priceTrends.data?.by_room_type.map((r) => r.room_type) ?? [];
  const notReady = exercises.isError || (exercises.data != null && list.length === 0);

  return (
    <div className="flex h-full flex-col bg-background">
      {/* Header */}
      <header className="flex items-center justify-between gap-3 border-b border-border bg-card px-5 py-3">
        <div className="flex items-center gap-3">
          <button type="button" onClick={onBack}
            className="flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium hover:bg-muted">
            <ArrowLeft className="h-3.5 w-3.5" /> Change
          </button>
          <div>
            <h1 className="text-base font-bold leading-tight">
              {tab === "exercises" ? "BTO Sales Exercises" : "Upcoming HDB Resale Supply"}
            </h1>
            <p className="text-xs text-muted-foreground">
              {tab === "exercises"
                ? "Flat supply, applications & subscription rates"
                : "Estimated BTO resale availability — when newer estates may enter the resale market"}
            </p>
          </div>
          <div className="ml-2 flex rounded-md border border-border p-0.5 text-xs">
            {([["exercises", "Sales Exercises"], ["supply", "Resale Availability"]] as const).map(([k, label]) => (
              <button key={k} type="button" onClick={() => setTab(k)}
                className={`rounded px-2.5 py-1 font-medium ${tab === k ? "bg-primary text-primary-foreground" : "hover:bg-muted"}`}>
                {label}
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {tab === "exercises" && list.length > 0 && (
            <select
              value={activeId ?? ""}
              onChange={(e) => setSelected(e.target.value)}
              className="h-8 rounded-md border border-input bg-background px-2 text-xs"
            >
              {list.map((e) => <option key={e.exercise_id} value={e.exercise_id}>{e.label}</option>)}
            </select>
          )}
          <button type="button" onClick={onToggleTheme} title="Toggle theme"
            className="flex h-8 w-8 items-center justify-center rounded-md border border-border hover:bg-muted">
            {theme === "light" ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
          </button>
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto p-5">
        {tab === "supply" ? (
          <div className="mx-auto max-w-5xl"><BtoResaleSupply /></div>
        ) : notReady ? (
          <div className="rounded-md border border-dashed border-border bg-muted/40 p-4 text-sm text-muted-foreground">
            No BTO data yet. Run <code className="rounded bg-muted px-1 py-0.5 text-xs">python -m app.data.bto</code> on the server (needs PostGIS).
          </div>
        ) : (
          <div className="mx-auto max-w-5xl space-y-5">
            {/* Summary */}
            {ex && (
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <Stat icon={Flame} label="Overall app rate" value={ex.overall_app_rate != null ? `${ex.overall_app_rate.toFixed(1)}×` : "—"} hint={ex.label} />
                <Stat icon={Building2} label="Units offered" value={ex.total_units.toLocaleString()} />
                <Stat icon={Users} label="Applicants" value={ex.total_applicants.toLocaleString()} />
                <Stat icon={Layers} label="Estates" value={String(ex.estate_count)} />
              </div>
            )}

            {/* Trend */}
            <div className="rounded-xl border border-border bg-card p-4">
              <h2 className="mb-3 text-sm font-semibold">Overall application rate by exercise</h2>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} unit="×" />
                    <Tooltip formatter={(v: number) => [`${v}×`, "App rate"]} />
                    <Bar dataKey="rate" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <p className="mt-1 text-[10px] text-muted-foreground">
                Applicants per flat. Higher = more competitive. {trends.data?.exercise_count ?? 0} exercise(s) tracked — grows each launch.
              </p>
            </div>

            {/* Price ranges over time */}
            {priceTrends.data && priceData.length > 0 && (
              <div className="rounded-xl border border-border bg-card p-4">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                  <h2 className="text-sm font-semibold">
                    BTO price by room type {priceTown ? `— ${priceTown}` : "(avg across towns)"}
                  </h2>
                  <select
                    value={priceTown}
                    onChange={(e) => setPriceTown(e.target.value)}
                    className="h-8 rounded-md border border-input bg-background px-2 text-xs"
                  >
                    <option value="">All towns (average)</option>
                    {(priceTrends.data.towns ?? []).map((t) => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={priceData} margin={{ top: 5, right: 10, left: 5, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                      <XAxis dataKey="year" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `$${Math.round(v / 1000)}k`} width={48} />
                      <Tooltip formatter={(v: number) => `$${v.toLocaleString()}`} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      {priceRoomTypes.map((rt) => (
                        <Line key={rt} type="monotone" dataKey={rt} stroke={ROOM_COLORS[rt] ?? "#888"}
                          strokeWidth={2} dot={false} connectNulls />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                <p className="mt-1 text-[10px] text-muted-foreground">
                  Midpoint of the offered price range per financial year. Source: data.gov.sg (HDB).
                </p>
              </div>
            )}

            {/* Oversubscription table */}
            {detail.data && (
              <div className="rounded-xl border border-border bg-card p-4">
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="text-sm font-semibold">Subscription by estate &amp; flat type — {ex?.label}</h2>
                  <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                    {[["≤1×", "bg-emerald-400"], ["≤3×", "bg-yellow-400"], ["≤5×", "bg-orange-400"], [">5×", "bg-red-400"]].map(([l, c]) => (
                      <span key={l} className="flex items-center gap-1"><span className={`h-2 w-2 rounded-full ${c}`} />{l}</span>
                    ))}
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse text-xs">
                    <thead>
                      <tr className="border-b border-border text-left text-muted-foreground">
                        <th className="py-1.5 pr-2 font-medium">Estate</th>
                        <th className="py-1.5 pr-2 font-medium">Flat type</th>
                        <th className="py-1.5 pr-2 font-medium">Class</th>
                        <th className="py-1.5 pr-2 text-right font-medium">Units</th>
                        <th className="py-1.5 pr-2 text-right font-medium">Apps</th>
                        <th className="py-1.5 pr-2 text-right font-medium">Overall</th>
                        <th className="py-1.5 pr-2 text-right font-medium">1st-timer fam</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.data.rates.map((r: BtoRate) => (
                        <tr key={r.id} className="border-b border-border/50">
                          <td className="py-1.5 pr-2 font-medium">{r.estate_name}</td>
                          <td className="py-1.5 pr-2">{r.flat_type}</td>
                          <td className="py-1.5 pr-2 text-muted-foreground">{r.classification ?? "—"}</td>
                          <td className="py-1.5 pr-2 text-right tabular-nums">{r.flat_supply.toLocaleString()}</td>
                          <td className="py-1.5 pr-2 text-right tabular-nums">{r.total_applicant_no.toLocaleString()}</td>
                          <td className="py-1.5 pr-2 text-right">
                            <span className={`rounded px-1.5 py-0.5 font-semibold tabular-nums ${rateColor(r.overall_rate)}`}>
                              {r.overall_rate != null ? `${r.overall_rate.toFixed(1)}×` : "—"}
                            </span>
                          </td>
                          <td className="py-1.5 pr-2 text-right tabular-nums text-muted-foreground">
                            {r.rate_first_time_fam != null ? `${r.rate_first_time_fam.toFixed(1)}×` : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
            <p className="text-[10px] text-muted-foreground">
              Source: HDB Flat Portal. Updated automatically each sales exercise. Not affiliated with HDB.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
