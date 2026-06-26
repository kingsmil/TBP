import { useEffect, useMemo, useRef, useState } from "react";
import { MapContainer, TileLayer, Marker, useMap, useMapEvents } from "react-leaflet";
import { divIcon, type LatLngBoundsExpression } from "leaflet";
import useSupercluster from "use-supercluster";
import type { CardItem } from "./types";
import { MODE_META } from "./types";

const GREY_TILES = "https://www.onemap.gov.sg/maps/tiles/Grey/{z}/{x}/{y}.png";
const SG_CENTER: [number, number] = [1.352, 103.82];

// Stable module-level identity — a new options object each render makes
// use-supercluster rebuild its index and emit a new clusters array every render,
// which feeds a render loop (the flicker).
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
  // Pan only when the *selection* changes — not on every render.
  useEffect(() => {
    if (!item) { last.current = null; return; }
    if (item.id === last.current || item.lat == null || item.lon == null) return;
    last.current = item.id;
    map.panTo([item.lat, item.lon], { animate: true, duration: 0.5 });
  }, [item, map]);
  return null;
}

/** Fit to the pins once per `fitKey` (e.g. the mode), when they first arrive —
 *  so switching modes re-centres on that mode's pins instead of staying put. */
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
          <Marker key={it.id} position={[lat, lon]} icon={pinIcon(it, it.id === selectedId)}
            eventHandlers={{ click: () => onSelect(it.id === selectedId ? null : it.id) }} />
        );
      })}
    </>
  );
}

export default function BakeoffMap({ items, selectedId, onSelect, fitKey }: Props) {
  const pts = useMemo(
    () => items.filter((i) => i.lat != null && i.lon != null).map((i) => [i.lat!, i.lon!] as [number, number]),
    [items],
  );
  const selected = useMemo(() => items.find((i) => i.id === selectedId) ?? null, [items, selectedId]);

  return (
    <MapContainer center={SG_CENTER} zoom={12} zoomControl={false}
      className="h-full w-full" style={{ background: "#e8edf0" }} preferCanvas>
      <TileLayer url={GREY_TILES} />
      <FitOnce pts={pts} fitKey={fitKey} />
      <Recenter item={selected} />
      <Clusters items={items} selectedId={selectedId} onSelect={onSelect} />
    </MapContainer>
  );
}
