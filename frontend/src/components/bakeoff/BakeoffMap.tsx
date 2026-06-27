import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueries } from "@tanstack/react-query";
import { MapContainer, TileLayer, Marker, CircleMarker, Circle, Polyline, Tooltip, Pane, useMap, useMapEvents } from "react-leaflet";
import { divIcon, type LatLngBoundsExpression } from "leaflet";
import useSupercluster from "use-supercluster";
import { Layers, X } from "lucide-react";
import type { CardItem } from "./types";
import { MODE_META } from "./types";
import { getAmenityTypes, getAmenities, getReferenceLayer, getBusStopReach } from "../../lib/api";
import { distanceMetres } from "../../lib/geo";

const TRANSIT_RADIUS_M = 500;
const BUS_COLORS = ["#2563eb", "#7c3aed", "#db2777", "#ea580c", "#059669", "#0891b2"];
// Keyed by the short line code used in the reference data (line_name = "EW" etc.)
const MRT_COLORS: Record<string, string> = {
  EW: "#009645", NS: "#d42e12", NE: "#9900aa", CC: "#fa9e0d",
  DT: "#005ec4", TE: "#9d5b25", CG: "#009645", BP: "#748477",
};

const GREY_TILES = "https://www.onemap.gov.sg/maps/tiles/Grey/{z}/{x}/{y}.png";
const SG_CENTER: [number, number] = [1.352, 103.82];
// Lock panning to mainland SG (+ nearby islands). Excludes the Pedra Branca
// "inset" OneMap draws far east (~104.3°E) and keeps white/empty areas off-screen.
const SG_BOUNDS: [[number, number], [number, number]] = [[1.16, 103.59], [1.47, 104.09]];

const AMENITY_EMOJI: Record<string, string> = {
  schools: "🎓", parks: "🌳", hawker: "🍜", hospitals: "🏥",
  sports: "⚽", community: "🏛️", library: "📚",
};

// Stable module-level identity — a new options object each render makes
// use-supercluster rebuild its index and emit a new clusters array every render.
const CLUSTER_OPTIONS = {
  radius: 70, maxZoom: 17, minPoints: 4,
  map: (props: any) => ({ minPrice: props.price }),
  reduce: (acc: any, props: any) => { acc.minPrice = Math.min(acc.minPrice, props.minPrice); },
};

function fmt(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(n >= 10_000_000 ? 0 : 1)}M`;
  return `$${Math.round(n / 1000)}k`;
}
function priceLabel(it: CardItem): string {
  if (it.pinLabel) return it.pinLabel;
  return it.price == null ? (it.badge ?? "View") : fmt(it.price);
}

function scoreColor(s: number): string {
  if (s >= 75) return "#16a34a";
  if (s >= 60) return "#65a30d";
  if (s >= 45) return "#f59e0b";
  if (s >= 30) return "#ea580c";
  return "#dc2626";
}

function pinIcon(it: CardItem, selected: boolean, colorByScore: boolean) {
  if (colorByScore && it.score != null) {
    const c = scoreColor(it.score);
    return divIcon({
      className: "bo-pin-wrap",
      html: `<div class="bo-pin ${selected ? "bo-pin--selected" : ""}" style="background:${c};color:#fff;border-color:${c}">${priceLabel(it)}</div>`,
      iconSize: [10, 10], iconAnchor: [0, 0],
    });
  }
  const dot = `<span class="bo-pin-dot" style="background:${MODE_META[it.mode].color}"></span>`;
  return divIcon({
    className: "bo-pin-wrap",
    html: `<div class="bo-pin ${selected ? "bo-pin--selected" : ""}">${dot}${priceLabel(it)}</div>`,
    iconSize: [10, 10], iconAnchor: [0, 0],
  });
}
function clusterIcon(count: number, from?: number) {
  const big = count >= 100;
  return divIcon({
    className: "bo-pin-wrap",
    html: `<div class="bo-cluster ${big ? "bo-cluster--lg" : ""}">
      <span class="bo-cluster__n">${count}</span>
      ${from != null ? `<span class="bo-cluster__from">from ${fmt(from)}</span>` : ""}
    </div>`,
    iconSize: [10, 10], iconAnchor: [0, 0],
  });
}

/** Zoom in + centre on the selected property; restore the previous view (centre
 *  + zoom) on deselect. */
function FocusView({ item }: { item: CardItem | null }) {
  const map = useMap();
  const lastId = useRef<string | null>(null);
  const prevView = useRef<{ center: [number, number]; zoom: number } | null>(null);
  useEffect(() => {
    const id = item?.id ?? null;
    if (id === lastId.current) return;
    if (id && item && item.lat != null && item.lon != null) {
      // Save the view before the first selection (not when switching A -> B).
      if (lastId.current === null) {
        const c = map.getCenter();
        prevView.current = { center: [c.lat, c.lng], zoom: map.getZoom() };
      }
      lastId.current = id;
      map.flyTo([item.lat, item.lon], Math.max(map.getZoom(), 16), { duration: 0.6 });
    } else {
      lastId.current = null;
      if (prevView.current) {
        map.flyTo(prevView.current.center, prevView.current.zoom, { duration: 0.6 });
        prevView.current = null;
      }
    }
  }, [item, map]);
  return null;
}

function FitOnce({ pts, fitKey }: { pts: [number, number][]; fitKey?: string }) {
  const map = useMap();
  const lastKey = useRef<string | undefined>(undefined);
  const fitted = useRef(false);
  useEffect(() => {
    if (fitKey !== lastKey.current) { lastKey.current = fitKey; fitted.current = false; }
    if (!fitted.current && pts.length > 0) {
      fitted.current = true;
      if (pts.length > 1) map.fitBounds(pts as LatLngBoundsExpression, { padding: [50, 50], maxZoom: 15 });
      else map.setView(pts[0], 15, { animate: true });
    }
  }, [fitKey, pts, map]);
  return null;
}

function amenityIcon(emoji: string, color: string, delayMs: number) {
  return divIcon({
    className: "bo-pin-wrap",
    html: `<div class="bo-amenity-bubble" style="--c:${color};animation-delay:${delayMs}ms"><span>${emoji}</span></div>`,
    iconSize: [24, 24], iconAnchor: [0, 0],
  });
}

/** Amenity POIs (schools, parks, hawker, …) as pins that drop in. When a property
 *  is selected (origin set), only the ones within the radius of it are shown —
 *  "what's near this estate"; otherwise all of that type island-wide. Default
 *  marker pane (z600), above the transit overlay (z560). */
function AmenityMarkers({ active, colorOf, origin }: {
  active: string[]; colorOf: (k: string) => string; origin: { lat: number; lon: number } | null;
}) {
  const queries = useQueries({
    queries: active.map((key) => ({
      queryKey: ["bo-amenity", key], queryFn: () => getAmenities(key), staleTime: 6e5,
    })),
  });
  // Hold the pins until the fly-to-estate finishes, so they drop in *after* the
  // map has zoomed/centred (re-triggered whenever the selected estate changes).
  const [ready, setReady] = useState(false);
  useEffect(() => {
    setReady(false);
    const t = setTimeout(() => setReady(true), 620);
    return () => clearTimeout(t);
  }, [origin?.lat, origin?.lon]);

  // Only show amenities when a property is selected — and only the ones near it.
  if (!origin || !ready) return null;
  return (
    <>
      {queries.map((q, i) => {
        const results = (q.data?.results ?? []).filter(
          (poi) => distanceMetres(origin, { lat: poi.lat, lon: poi.lon }) <= TRANSIT_RADIUS_M);
        return results.map((poi, j) => (
          <Marker key={`${active[i]}-${poi.lat}-${poi.lon}`} position={[poi.lat, poi.lon]}
            icon={amenityIcon(AMENITY_EMOJI[active[i]] ?? "📍", colorOf(active[i]), (j % 16) * 40)}>
            <Tooltip direction="top" offset={[0, -10]}>{AMENITY_EMOJI[active[i]] ?? ""} {poi.name}</Tooltip>
          </Marker>
        ));
      })}
    </>
  );
}

/** On-select transit: nearby bus stops + where their buses go + nearby MRT lines,
 *  within a radius of the selected property. */
function TransitLayer({ item }: { item: CardItem }) {
  const origin = { lat: item.lat!, lon: item.lon! };
  const busStops = useQuery({ queryKey: ["reference", "bus_stops"], queryFn: () => getReferenceLayer("bus_stops"), staleTime: 6e5 });
  const mrt = useQuery({ queryKey: ["reference", "mrt"], queryFn: () => getReferenceLayer("mrt"), staleTime: 6e5 });

  const nearbyStops = useMemo(() => {
    const out: { code: string; lat: number; lon: number; d: number }[] = [];
    for (const f of busStops.data?.features ?? []) {
      const [lon, lat] = f.geometry.coordinates;
      const d = distanceMetres(origin, { lat, lon });
      if (d <= TRANSIT_RADIUS_M) out.push({ code: String(f.properties.code ?? ""), lat, lon, d });
    }
    return out.filter((s) => s.code).sort((a, b) => a.d - b.d).slice(0, 8);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [busStops.data, item.lat, item.lon]);

  const mrtLines = useMemo(() => {
    const lines = new Map<string, { sid: number; lat: number; lon: number }[]>();
    for (const f of mrt.data?.features ?? []) {
      const line = String(f.properties.line_name ?? "");
      const sid = Number(f.properties.station_id);
      if (!line || !Number.isFinite(sid)) continue;
      const [lon, lat] = f.geometry.coordinates;
      const arr = lines.get(line) ?? [];
      arr.push({ sid, lat, lon });
      lines.set(line, arr);
    }
    for (const arr of lines.values()) arr.sort((a, b) => a.sid - b.sid);
    return lines;
  }, [mrt.data]);

  const nearbyMrtLines = useMemo(() => {
    const names: string[] = [];
    for (const [line, stations] of mrtLines) {
      if (stations.some((s) => distanceMetres(origin, s) <= TRANSIT_RADIUS_M)) names.push(line);
    }
    return names;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mrtLines, item.lat, item.lon]);

  const reachQueries = useQueries({
    queries: nearbyStops.map((s) => ({
      queryKey: ["bo-reach", s.code], queryFn: () => getBusStopReach(s.code), staleTime: 3e5,
    })),
  });
  const routes = reachQueries.flatMap((q) => q.data?.services ?? []);

  return (
    // Below the property pins (markerPane z600) so the selected estate sits on top.
    <Pane name="bo-transit" style={{ zIndex: 560, pointerEvents: "none" }}>
      <Circle center={[origin.lat, origin.lon]} radius={TRANSIT_RADIUS_M} interactive={false}
        pathOptions={{ color: "#2563eb", fillColor: "#60a5fa", fillOpacity: 0.06, dashArray: "6 5", weight: 1.5 }} />
      {nearbyMrtLines.map((line) => {
        const positions = (mrtLines.get(line) ?? []).map((s) => [s.lat, s.lon] as [number, number]);
        const color = MRT_COLORS[line] ?? "#334155";
        return (
          <Fragment key={`mrt-${line}`}>
            <Polyline positions={positions} interactive={false} pathOptions={{ color: "#fff", weight: 14, opacity: 0.9, lineCap: "round", lineJoin: "round" }} />
            <Polyline positions={positions} interactive={false} pathOptions={{ color, weight: 9, opacity: 1, lineCap: "round", lineJoin: "round" }} />
          </Fragment>
        );
      })}
      {routes.map((svc, i) => {
        const positions = svc.stops.map((s) => [s.lat, s.lon] as [number, number]);
        const color = BUS_COLORS[i % BUS_COLORS.length];
        return (
          <Fragment key={`bus-${svc.service_no}-${svc.direction}-${i}`}>
            <Polyline positions={positions} interactive={false} pathOptions={{ color: "#fff", weight: 8, opacity: 0.75, dashArray: "10 8", lineCap: "round" }} />
            <Polyline positions={positions} interactive={false} pathOptions={{ color, weight: 4.5, opacity: 0.95, dashArray: "10 8", lineCap: "round" }} />
          </Fragment>
        );
      })}
      {nearbyStops.map((s) => (
        <CircleMarker key={`stop-${s.code}`} center={[s.lat, s.lon]} radius={7} interactive={false}
          pathOptions={{ pane: "bo-transit", color: "#1e3a8a", fillColor: "#facc15", fillOpacity: 0.95, weight: 2 }} />
      ))}
    </Pane>
  );
}

interface Props {
  items: CardItem[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  fitKey?: string;
  colorByScore?: boolean;
}

function Clusters({ items, selectedId, onSelect, colorByScore }: Omit<Props, "fitKey">) {
  const map = useMap();
  const [bounds, setBounds] = useState<[number, number, number, number]>([103.6, 1.13, 104.01, 1.48]);
  const [zoom, setZoom] = useState(12);

  const update = () => {
    const b = map.getBounds();
    setBounds([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]);
    setZoom(map.getZoom());
  };
  useEffect(update, []); // eslint-disable-line react-hooks/exhaustive-deps
  useMapEvents({ moveend: update, zoomend: update });

  const points = useMemo(
    () => items.filter((i) => i.lat != null && i.lon != null).map((i) => ({
      type: "Feature" as const,
      properties: { cluster: false as const, item: i, price: i.price ?? Infinity },
      geometry: { type: "Point" as const, coordinates: [i.lon!, i.lat!] },
    })),
    [items],
  );

  const { clusters, supercluster } = useSupercluster({
    points, bounds, zoom, options: CLUSTER_OPTIONS,
  });

  // Focus mode: when a property is selected, show only its pin so you can focus
  // on it + its surroundings (others hide, like the classic map).
  const selected = selectedId ? items.find((i) => i.id === selectedId && i.lat != null) : null;
  if (selected) {
    return (
      <Marker key={selected.id} position={[selected.lat!, selected.lon!]} icon={pinIcon(selected, true, !!colorByScore)}
        eventHandlers={{ click: () => onSelect(null) }} />
    );
  }

  return (
    <>
      {clusters.map((c: any) => {
        const [lon, lat] = c.geometry.coordinates;
        const { cluster: isCluster, cluster_id, point_count, minPrice, item } = c.properties;
        if (isCluster) {
          const from = Number.isFinite(minPrice) ? minPrice : undefined;
          return (
            <Marker key={`c-${cluster_id}`} position={[lat, lon]} icon={clusterIcon(point_count, from)}
              eventHandlers={{ click: () => {
                const z = Math.min(supercluster!.getClusterExpansionZoom(cluster_id), 17);
                map.setView([lat, lon], z, { animate: true });
              } }} />
          );
        }
        const it: CardItem = item;
        return (
          <Marker key={it.id} position={[lat, lon]} icon={pinIcon(it, false, !!colorByScore)}
            eventHandlers={{ click: () => onSelect(it.id) }} />
        );
      })}
    </>
  );
}

/** Floating glass panel of amenity-layer toggles. */
function AmenityToggle({ active, onToggle }: { active: string[]; onToggle: (k: string) => void }) {
  const [open, setOpen] = useState(false);
  const types = useQuery({ queryKey: ["amenity-types"], queryFn: getAmenityTypes, staleTime: 6e5 });
  const list = types.data?.amenities ?? [];
  return (
    <div className="absolute bottom-24 left-3 z-[1000] sm:bottom-3 sm:left-[21rem]">
      {open && list.length > 0 && (
        <div className="bo-glass mb-2 w-52 rounded-2xl p-2">
          <div className="mb-1 flex items-center justify-between px-1">
            <span className="text-[11px] font-bold uppercase tracking-wide text-muted-foreground">Amenities</span>
            <button type="button" onClick={() => setOpen(false)} className="rounded p-0.5 hover:bg-muted"><X className="h-3.5 w-3.5" /></button>
          </div>
          <div className="flex flex-wrap gap-1.5 p-1">
            {list.map((a) => {
              const on = active.includes(a.key);
              return (
                <button key={a.key} type="button" onClick={() => onToggle(a.key)}
                  className={`rounded-full border px-2 py-1 text-xs font-medium transition-colors ${on ? "text-white" : "border-border bg-card hover:bg-muted"}`}
                  style={on ? { background: a.color, borderColor: a.color } : undefined}>
                  {AMENITY_EMOJI[a.key] ?? ""} {a.label}
                </button>
              );
            })}
          </div>
        </div>
      )}
      <button type="button" onClick={() => setOpen((o) => !o)}
        className="bo-glass flex items-center gap-2 rounded-full px-3.5 py-2.5 text-sm font-semibold shadow-sm">
        <Layers className="h-4 w-4" /> Amenities{active.length > 0 ? ` · ${active.length}` : ""}
      </button>
    </div>
  );
}

export default function BakeoffMap({ items, selectedId, onSelect, fitKey, colorByScore }: Props) {
  const [activeAmenities, setActiveAmenities] = useState<string[]>([]);
  const types = useQuery({ queryKey: ["amenity-types"], queryFn: getAmenityTypes, staleTime: 6e5 });
  const colorOf = (key: string) => types.data?.amenities.find((a) => a.key === key)?.color ?? "#475569";
  // All amenity layers on by default (once the types load).
  const amenitiesInited = useRef(false);
  useEffect(() => {
    if (!amenitiesInited.current && types.data?.amenities?.length) {
      amenitiesInited.current = true;
      setActiveAmenities(types.data.amenities.map((a) => a.key));
    }
  }, [types.data]);
  const toggleAmenity = (key: string) =>
    setActiveAmenities((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]));

  const pts = useMemo(
    () => items.filter((i) => i.lat != null && i.lon != null).map((i) => [i.lat!, i.lon!] as [number, number]),
    [items],
  );
  const selected = useMemo(() => items.find((i) => i.id === selectedId) ?? null, [items, selectedId]);

  return (
    <div className="relative h-full w-full">
      <MapContainer center={SG_CENTER} zoom={12} zoomControl={false}
        minZoom={11} maxBounds={SG_BOUNDS} maxBoundsViscosity={1}
        className="h-full w-full" style={{ background: "#e8edf0" }} preferCanvas>
        <TileLayer url={GREY_TILES} bounds={SG_BOUNDS} noWrap />
        <FitOnce pts={pts} fitKey={fitKey} />
        <FocusView item={selected} />
        <Clusters items={items} selectedId={selectedId} onSelect={onSelect} colorByScore={colorByScore} />
        {selected && selected.lat != null && selected.lon != null && <TransitLayer item={selected} />}
        {activeAmenities.length > 0 && (
          <AmenityMarkers active={activeAmenities} colorOf={colorOf}
            origin={selected && selected.lat != null && selected.lon != null ? { lat: selected.lat, lon: selected.lon } : null} />
        )}
      </MapContainer>
      <AmenityToggle active={activeAmenities} onToggle={toggleAmenity} />
    </div>
  );
}
