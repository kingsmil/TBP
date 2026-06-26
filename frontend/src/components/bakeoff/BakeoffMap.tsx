import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueries } from "@tanstack/react-query";
import { MapContainer, TileLayer, Marker, CircleMarker, Tooltip, Pane, useMap, useMapEvents } from "react-leaflet";
import { divIcon, type LatLngBoundsExpression } from "leaflet";
import useSupercluster from "use-supercluster";
import { Layers, X } from "lucide-react";
import type { CardItem } from "./types";
import { MODE_META } from "./types";
import { getAmenityTypes, getAmenities } from "../../lib/api";

const GREY_TILES = "https://www.onemap.gov.sg/maps/tiles/Grey/{z}/{x}/{y}.png";
const SG_CENTER: [number, number] = [1.352, 103.82];

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

function pinIcon(it: CardItem, selected: boolean) {
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

function Recenter({ item }: { item: CardItem | null }) {
  const map = useMap();
  const last = useRef<string | null>(null);
  useEffect(() => {
    if (!item) { last.current = null; return; }
    if (item.id === last.current || item.lat == null || item.lon == null) return;
    last.current = item.id;
    map.panTo([item.lat, item.lon], { animate: true, duration: 0.5 });
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

/** Amenity POIs (schools, parks, hawker, …) for the active layers. */
function AmenityMarkers({ active, colorOf }: { active: string[]; colorOf: (k: string) => string }) {
  const queries = useQueries({
    queries: active.map((key) => ({
      queryKey: ["bo-amenity", key], queryFn: () => getAmenities(key), staleTime: 6e5,
    })),
  });
  return (
    <Pane name="bo-amenities" style={{ zIndex: 560 }}>
      {queries.map((q, i) =>
        (q.data?.results ?? []).map((poi, j) => (
          <CircleMarker key={`${active[i]}-${j}`} center={[poi.lat, poi.lon]} radius={5}
            pane="bo-amenities"
            pathOptions={{ color: "#fff", weight: 1.5, fillColor: colorOf(active[i]), fillOpacity: 0.9 }}>
            <Tooltip direction="top">{AMENITY_EMOJI[active[i]] ?? ""} {poi.name}</Tooltip>
          </CircleMarker>
        )),
      )}
    </Pane>
  );
}

interface Props {
  items: CardItem[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  fitKey?: string;
}

function Clusters({ items, selectedId, onSelect }: Omit<Props, "fitKey">) {
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
      <Marker key={selected.id} position={[selected.lat!, selected.lon!]} icon={pinIcon(selected, true)}
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
          <Marker key={it.id} position={[lat, lon]} icon={pinIcon(it, false)}
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

export default function BakeoffMap({ items, selectedId, onSelect, fitKey }: Props) {
  const [activeAmenities, setActiveAmenities] = useState<string[]>([]);
  const types = useQuery({ queryKey: ["amenity-types"], queryFn: getAmenityTypes, staleTime: 6e5 });
  const colorOf = (key: string) => types.data?.amenities.find((a) => a.key === key)?.color ?? "#475569";
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
        className="h-full w-full" style={{ background: "#e8edf0" }} preferCanvas>
        <TileLayer url={GREY_TILES} />
        <FitOnce pts={pts} fitKey={fitKey} />
        <Recenter item={selected} />
        <Clusters items={items} selectedId={selectedId} onSelect={onSelect} />
        {activeAmenities.length > 0 && <AmenityMarkers active={activeAmenities} colorOf={colorOf} />}
      </MapContainer>
      <AmenityToggle active={activeAmenities} onToggle={toggleAmenity} />
    </div>
  );
}
