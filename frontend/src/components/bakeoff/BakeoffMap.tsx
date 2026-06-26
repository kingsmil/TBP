import { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, Marker, useMap, useMapEvents } from "react-leaflet";
import { divIcon, type LatLngBoundsExpression } from "leaflet";
import useSupercluster from "use-supercluster";
import type { CardItem } from "./types";

const GREY_TILES = "https://www.onemap.gov.sg/maps/tiles/Grey/{z}/{x}/{y}.png";
const SG_CENTER: [number, number] = [1.352, 103.82];

function fmt(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(n >= 10_000_000 ? 0 : 1)}M`;
  return `$${Math.round(n / 1000)}k`;
}
function priceLabel(it: CardItem): string {
  return it.price == null ? (it.badge ?? "View") : fmt(it.price);
}

function pinIcon(it: CardItem, state: "" | "selected" | "hover") {
  return divIcon({
    className: "bo-pin-wrap",
    html: `<div class="bo-pin ${state ? `bo-pin--${state}` : ""}">${priceLabel(it)}</div>`,
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
  useEffect(() => {
    if (item?.lat != null && item?.lon != null) map.panTo([item.lat, item.lon], { animate: true, duration: 0.5 });
  }, [item, map]);
  return null;
}

function FitOnce({ pts }: { pts: [number, number][] }) {
  const map = useMap();
  useEffect(() => {
    if (pts.length > 1) map.fitBounds(pts as LatLngBoundsExpression, { padding: [60, 60], maxZoom: 15 });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pts.length > 0]);
  return null;
}

interface Props {
  items: CardItem[];
  selectedId: string | null;
  hoveredId: string | null;
  onSelect: (id: string | null) => void;
}

function Clusters({ items, selectedId, hoveredId, onSelect }: Props) {
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
    points, bounds, zoom,
    options: {
      radius: 70, maxZoom: 17, minPoints: 4,
      map: (props: any) => ({ minPrice: props.price }),
      reduce: (acc: any, props: any) => { acc.minPrice = Math.min(acc.minPrice, props.minPrice); },
    },
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
        const state = it.id === selectedId ? "selected" : it.id === hoveredId ? "hover" : "";
        return (
          <Marker key={it.id} position={[lat, lon]} icon={pinIcon(it, state)}
            eventHandlers={{ click: () => onSelect(it.id === selectedId ? null : it.id) }} />
        );
      })}
    </>
  );
}

export default function BakeoffMap({ items, selectedId, hoveredId, onSelect }: Props) {
  const pts = useMemo(
    () => items.filter((i) => i.lat != null && i.lon != null).map((i) => [i.lat!, i.lon!] as [number, number]),
    [items],
  );
  const selected = useMemo(() => items.find((i) => i.id === selectedId) ?? null, [items, selectedId]);

  return (
    <MapContainer center={SG_CENTER} zoom={12} zoomControl={false}
      className="h-full w-full" style={{ background: "#e8edf0" }} preferCanvas>
      <TileLayer url={GREY_TILES} />
      <FitOnce pts={pts} />
      <Recenter item={selected} />
      <Clusters items={items} selectedId={selectedId} hoveredId={hoveredId} onSelect={onSelect} />
    </MapContainer>
  );
}
