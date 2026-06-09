import { useEffect, useRef, useState } from "react";
import { Bus, MapPin, Search, Train, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { findDirectTransitHomes, geocodeAddress } from "../lib/api";
import type { DirectTransitDestination, DirectTransitResponse, SearchFilters } from "../types";

interface Props {
  filters: SearchFilters;
  onResults: (results: DirectTransitResponse | null) => void;
}

export default function DirectTransitFilter({ filters, onResults }: Props) {
  const [query, setQuery] = useState("");
  const [label, setLabel] = useState("Workplace");
  const [suggestions, setSuggestions] = useState<Awaited<ReturnType<typeof geocodeAddress>>["results"]>([]);
  const [destinations, setDestinations] = useState<DirectTransitDestination[]>([]);
  const [walkMinutes, setWalkMinutes] = useState(6);
  const [modes, setModes] = useState<("bus" | "mrt")[]>(["bus", "mrt"]);
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState(false);
  const firstFilterRender = useRef(true);

  async function searchAddress() {
    if (query.trim().length < 2) return;
    setLoading(true);
    setStatus(null);
    try {
      const response = await geocodeAddress(query.trim());
      setSuggestions(response.results);
      if (!response.results.length) setStatus("No address results found.");
    } catch {
      setStatus("Address search failed.");
    } finally {
      setLoading(false);
    }
  }

  async function apply() {
    if (!destinations.length || !modes.length) return;
    setLoading(true);
    setStatus("Finding homes with direct transit...");
    try {
      const response = await findDirectTransitHomes({
        destinations,
        max_walk_minutes: walkMinutes,
        modes,
        town: filters.town,
        planning_area_id: filters.planning_area_id,
        flat_type: filters.flat_type,
        min_price: filters.min_price,
        max_price: filters.max_price,
        min_psf: filters.min_psf,
        max_psf: filters.max_psf,
        max_mrt_distance_m: filters.max_mrt_distance_m,
        min_schools_within_1km: filters.min_schools_within_1km,
        limit: 500,
      });
      onResults(response);
      setStatus(`${response.count} matching homes found.`);
    } catch {
      setStatus("Direct transit search failed.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (firstFilterRender.current) {
      firstFilterRender.current = false;
      return;
    }
    if (active && destinations.length && modes.length) void apply();
    // apply intentionally reruns with the latest shared filters.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  function toggleMode(mode: "bus" | "mrt") {
    setModes((current) => current.includes(mode)
      ? current.filter((item) => item !== mode)
      : [...current, mode]);
  }

  return (
    <div className="space-y-3 px-5 py-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold">Direct transit convenience</h2>
          <p className="text-xs text-muted-foreground">No transfers, with walking limits at both ends.</p>
        </div>
        {destinations.length > 0 && (
          <Button variant="ghost" size="sm" onClick={() => {
            setDestinations([]);
            setSuggestions([]);
            setStatus(null);
            setActive(false);
            onResults(null);
          }}>Clear</Button>
        )}
      </div>

      <div className="grid grid-cols-[110px_1fr_auto] gap-2">
        <Input value={label} onChange={(event) => setLabel(event.target.value)} placeholder="Workplace" />
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => { if (event.key === "Enter") void searchAddress(); }}
          placeholder="Address or place"
        />
        <Button size="icon" variant="outline" onClick={() => void searchAddress()} disabled={loading}>
          <Search className="h-4 w-4" />
        </Button>
      </div>

      {suggestions.length > 0 && (
        <div className="max-h-40 overflow-y-auto rounded-md border bg-background">
          {suggestions.map((result) => (
            <button
              type="button"
              key={`${result.lat}-${result.lon}-${result.label}`}
              onClick={() => {
                setDestinations((current) => [...current, {
                  name: label.trim() || result.label,
                  lat: result.lat,
                  lon: result.lon,
                }]);
                setQuery("");
                setSuggestions([]);
              }}
              className="flex w-full gap-2 border-b px-3 py-2 text-left text-xs last:border-0 hover:bg-muted"
            >
              <MapPin className="mt-0.5 h-3 w-3 shrink-0" /> {result.label}
            </button>
          ))}
        </div>
      )}

      {destinations.map((destination, index) => (
        <div key={`${destination.name}-${index}`} className="flex items-center justify-between rounded-md bg-muted px-3 py-2 text-xs">
          <span><strong>{destination.name}</strong> ({destination.lat.toFixed(4)}, {destination.lon.toFixed(4)})</span>
          <button type="button" onClick={() => setDestinations((items) => items.filter((_, i) => i !== index))}>
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}

      <div className="space-y-1.5">
        <Label htmlFor="walk-minutes">Maximum walk at each end (minutes)</Label>
        <Input id="walk-minutes" type="number" min={1} max={30} value={walkMinutes}
          onChange={(event) => setWalkMinutes(Number(event.target.value) || 1)} />
        <p className="text-xs text-muted-foreground">{walkMinutes} min = up to {walkMinutes * 80} m before and after transit.</p>
      </div>

      <div className="flex gap-2">
        <Button type="button" size="sm" variant={modes.includes("bus") ? "default" : "outline"} onClick={() => toggleMode("bus")}>
          <Bus className="mr-1 h-4 w-4" /> Bus
        </Button>
        <Button type="button" size="sm" variant={modes.includes("mrt") ? "default" : "outline"} onClick={() => toggleMode("mrt")}>
          <Train className="mr-1 h-4 w-4" /> MRT
        </Button>
      </div>

      <Button className="w-full" onClick={() => {
        setActive(true);
        void apply();
      }} disabled={loading || !destinations.length || !modes.length}>
        Apply all conditions
      </Button>
      <p className="text-xs text-muted-foreground">
        Transit requirements and the property filters above are combined with AND logic.
      </p>
      {status && <p className="text-xs text-muted-foreground">{status}</p>}
    </div>
  );
}
