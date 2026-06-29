import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { MapPin } from "lucide-react";
import { geocodeAddress } from "../../lib/api";
import { SearchBar } from "./shell";

function useDebounced<T>(value: T, ms: number): T {
  const [d, setD] = useState(value);
  useEffect(() => { const t = setTimeout(() => setD(value), ms); return () => clearTimeout(t); }, [value, ms]);
  return d;
}

interface Props {
  value: string;
  onChange: (v: string) => void;
  /** Fly the map to a geocoded place (postal code, address, MRT, area). */
  onPick: (lat: number, lon: number, label: string) => void;
}

/** Search bar that both filters the list (by name) and geocodes via OneMap, so
 *  you can jump to a postal code / address / MRT / area on the map. */
export default function LocationSearch({ value, onChange, onPick }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const dq = useDebounced(value, 250);

  const geo = useQuery({
    queryKey: ["bo-geocode", dq],
    queryFn: () => geocodeAddress(dq.trim()),
    enabled: open && dq.trim().length >= 3,
    staleTime: 6e5,
  });
  const results = geo.data?.results?.slice(0, 6) ?? [];

  useEffect(() => {
    const onDoc = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const pick = (r: { lat: number; lon: number; label: string }) => {
    onPick(r.lat, r.lon, r.label);
    setOpen(false);
  };

  return (
    <div ref={ref} className="relative flex-1">
      <div className="bo-glass flex items-center gap-2 rounded-full px-2 py-1.5">
        <SearchBar
          value={value}
          onChange={(v) => { onChange(v); setOpen(true); }}
          placeholder="Search postal code, address, MRT or area…"
        />
      </div>
      {open && value.trim().length >= 3 && (results.length > 0 || geo.isFetching) && (
        <div className="bo-glass absolute inset-x-0 top-[3.25rem] z-[1100] max-h-72 overflow-y-auto rounded-2xl p-1.5 shadow-lg">
          {geo.isFetching && results.length === 0 && (
            <div className="px-2.5 py-2 text-xs text-muted-foreground">Searching…</div>
          )}
          {results.map((r, i) => (
            <button key={i} type="button"
              onMouseDown={(e) => e.preventDefault()} onClick={() => pick(r)}
              className="flex w-full items-start gap-2 rounded-xl px-2.5 py-2 text-left text-xs hover:bg-muted">
              <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
              <span className="line-clamp-2">{r.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
