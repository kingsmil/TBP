import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ListOrdered, MapPin, Search, Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getScoreRankingFields, rankByScore, geocodeAddress } from "../lib/api";
import type { ScoreRankingRow, DestinationPayload } from "../types";

interface Props {
  /** Called with the ranked rows so the map can highlight them. */
  onResults: (rows: ScoreRankingRow[]) => void;
  /** Called when a result row is clicked. */
  onSelectBlock: (blockId: number) => void;
}

interface DestRow extends DestinationPayload {
  address?: string;
}

export default function ScoreRankingPanel({ onResults, onSelectBlock }: Props) {
  const { data, isLoading: fieldsLoading } = useQuery({
    queryKey: ["score-ranking-fields"],
    queryFn: getScoreRankingFields,
    staleTime: 1000 * 60 * 60,
  });
  const fields = data?.fields ?? [];

  const [weights, setWeights] = useState<Record<string, number>>({});
  const [destinations, setDestinations] = useState<DestRow[]>([]);
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<Awaited<ReturnType<typeof geocodeAddress>>["results"]>([]);
  const [results, setResults] = useState<ScoreRankingRow[] | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Default each field's weight from the server spec the first time fields load.
  const effectiveWeights = useMemo(() => {
    const merged: Record<string, number> = {};
    for (const f of fields) {
      merged[f.key] = weights[f.key] ?? f.default_weight;
    }
    return merged;
  }, [fields, weights]);

  const transportField = fields.find((f) => f.needs_destinations);
  const transportWeighted =
    transportField != null && (effectiveWeights[transportField.key] ?? 0) > 0;

  const anyWeighted = fields.some(
    (f) => !f.coming_soon && (effectiveWeights[f.key] ?? 0) > 0,
  );
  const needDestination = transportWeighted && destinations.length === 0;

  function setWeight(key: string, value: number) {
    setWeights((w) => ({ ...w, [key]: value }));
  }

  async function searchAddress() {
    if (query.trim().length < 2) return;
    try {
      const res = await geocodeAddress(query.trim());
      setSuggestions(res.results);
      if (!res.results.length) setStatus("No address results found.");
    } catch {
      setStatus("Address search failed.");
    }
  }

  async function rank() {
    if (!anyWeighted || needDestination) return;
    setLoading(true);
    setStatus("Scoring and ranking properties…");
    try {
      const weightsToSend: Record<string, number> = {};
      for (const f of fields) {
        if (!f.coming_soon && (effectiveWeights[f.key] ?? 0) > 0) {
          weightsToSend[f.key] = effectiveWeights[f.key];
        }
      }
      const res = await rankByScore({
        weights: weightsToSend,
        destinations: destinations.map((d) => ({
          name: d.name,
          lat: d.lat,
          lon: d.lon,
          visits_per_week: d.visits_per_week,
        })),
        limit: 50,
      });
      setResults(res.results);
      onResults(res.results);
      setStatus(
        res.count > 0
          ? `Ranked ${res.count} properties — showing top ${res.results.length}.`
          : "No properties matched the selected factors.",
      );
    } catch {
      setStatus("Ranking failed — is the API running?");
    } finally {
      setLoading(false);
    }
  }

  function clearAll() {
    setResults(null);
    onResults([]);
    setStatus(null);
  }

  return (
    <div className="space-y-3 px-5 py-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="flex items-center gap-1.5 text-sm font-semibold">
            <ListOrdered className="h-4 w-4" /> Score ranking
          </h2>
          <p className="text-xs text-muted-foreground">
            Slide to weight what matters; we rank every block by your mix.
          </p>
        </div>
        {results && (
          <Button variant="ghost" size="sm" onClick={clearAll}>Clear</Button>
        )}
      </div>

      {fieldsLoading && <p className="text-xs text-muted-foreground">Loading factors…</p>}

      {/* Weight sliders */}
      <div className="space-y-3">
        {fields.map((f) => {
          const value = effectiveWeights[f.key] ?? 0;
          const disabled = f.coming_soon;
          return (
            <div key={f.key} className={disabled ? "opacity-50" : undefined}>
              <div className="flex items-center justify-between gap-2">
                <label htmlFor={`w-${f.key}`} className="text-xs font-medium text-foreground">
                  {f.label}
                  {f.coming_soon && (
                    <span className="ml-1.5 rounded bg-muted px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                      Coming soon
                    </span>
                  )}
                </label>
                <span className="tabular-nums text-[11px] text-muted-foreground">{disabled ? "—" : value}</span>
              </div>
              <input
                id={`w-${f.key}`}
                type="range"
                min={0}
                max={100}
                step={5}
                value={disabled ? 0 : value}
                disabled={disabled}
                onChange={(e) => setWeight(f.key, Number(e.target.value))}
                className="mt-1 w-full accent-primary disabled:cursor-not-allowed"
                title={f.description}
              />
              <p className="mt-0.5 text-[10px] leading-tight text-muted-foreground">{f.description}</p>

              {/* Transport destinations + frequency, revealed when weighted */}
              {f.needs_destinations && !disabled && value > 0 && (
                <div className="mt-2 space-y-2 rounded-md border border-border bg-muted/40 p-2">
                  <div className="grid grid-cols-[1fr_auto] gap-2">
                    <Input
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); void searchAddress(); } }}
                      placeholder="Add a place you go (work, parents…)"
                      className="h-8 text-xs"
                    />
                    <Button size="icon" variant="outline" className="h-8 w-8" onClick={() => void searchAddress()}>
                      <Search className="h-3.5 w-3.5" />
                    </Button>
                  </div>

                  {suggestions.length > 0 && (
                    <div className="max-h-32 overflow-y-auto rounded-md border bg-background">
                      {suggestions.map((r) => (
                        <button
                          type="button"
                          key={`${r.lat}-${r.lon}-${r.label}`}
                          onClick={() => {
                            setDestinations((cur) => [...cur, {
                              name: r.label, address: r.label, lat: r.lat, lon: r.lon, visits_per_week: 5,
                            }]);
                            setQuery("");
                            setSuggestions([]);
                          }}
                          className="flex w-full gap-2 border-b px-2 py-1.5 text-left text-[11px] last:border-0 hover:bg-muted"
                        >
                          <MapPin className="mt-0.5 h-3 w-3 shrink-0" /> {r.label}
                        </button>
                      ))}
                    </div>
                  )}

                  {destinations.map((d, i) => (
                    <div key={`${d.name}-${i}`} className="flex items-center gap-2 rounded-md bg-background px-2 py-1.5 text-[11px]">
                      <div className="min-w-0 flex-1">
                        <div className="truncate font-medium">{d.name}</div>
                      </div>
                      <div className="flex shrink-0 items-center gap-1">
                        <input
                          type="number"
                          min={1}
                          max={21}
                          value={d.visits_per_week}
                          onChange={(e) => {
                            const v = Math.max(1, Number(e.target.value) || 1);
                            setDestinations((cur) => cur.map((x, xi) => xi === i ? { ...x, visits_per_week: v } : x));
                          }}
                          className="h-7 w-12 rounded border border-input bg-background px-1 text-center text-[11px]"
                          title="Round trips per week"
                        />
                        <span className="text-muted-foreground">×/wk</span>
                      </div>
                      <button
                        type="button"
                        aria-label={`Remove ${d.name}`}
                        onClick={() => setDestinations((cur) => cur.filter((_, xi) => xi !== i))}
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))}
                  {needDestination && (
                    <p className="text-[10px] text-amber-600">Add at least one place to score transport.</p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <Button className="w-full" onClick={() => void rank()} disabled={loading || !anyWeighted || needDestination}>
        <Sparkles className="mr-1.5 h-4 w-4" />
        {loading ? "Ranking…" : "Rank properties"}
      </Button>
      {status && <p className="text-xs text-muted-foreground">{status}</p>}

      {/* Ranked results */}
      {results && results.length > 0 && (
        <div className="space-y-1.5 pt-1">
          {results.map((r) => (
            <button
              type="button"
              key={r.block_id}
              onClick={() => onSelectBlock(r.block_id)}
              className="flex w-full items-center gap-2.5 rounded-md border border-border bg-card px-2.5 py-2 text-left hover:bg-muted"
            >
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[11px] font-bold text-primary">
                {r.rank}
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-xs font-semibold">{r.block_number} {r.street_name}</div>
                <div className="truncate text-[10px] text-muted-foreground">{r.town}</div>
              </div>
              <span className="shrink-0 tabular-nums text-sm font-bold text-foreground">{Math.round(r.overall_score)}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
