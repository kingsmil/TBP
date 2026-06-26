import { useEffect, useMemo } from "react";
import { MapContainer, TileLayer, Marker, useMap } from "react-leaflet";
import { divIcon, type LatLngBoundsExpression } from "leaflet";
import type { CardItem } from "./types";

const GREY_TILES = "https://www.onemap.gov.sg/maps/tiles/Grey/{z}/{x}/{y}.png";
const SG_CENTER: [number, number] = [1.352, 103.82];

function priceLabel(it: CardItem): string {
  if (it.price == null) return it.badge ?? "View";
  if (it.price >= 1_000_000) return `$${(it.price / 1_000_000).toFixed(it.price >= 10_000_000 ? 0 : 1)}M`;
  return `$${Math.round(it.price / 1000)}k`;
}

function makeIcon(it: CardItem, state: "" | "selected" | "hover") {
  const cls = `bo-pin ${state ? `bo-pin--${state}` : ""}`;
  return divIcon({
    className: "bo-pin-wrap",
    html: `<div class="${cls}">${priceLabel(it)}</div>`,
    iconSize: [10, 10],
    iconAnchor: [0, 0],
  });
}

/** Pans to the selected item without changing zoom. */
function Recenter({ item }: { item: CardItem | null }) {
  const map = useMap();
  useEffect(() => {
    if (item?.lat != null && item?.lon != null) {
      map.panTo([item.lat, item.lon], { animate: true, duration: 0.5 });
    }
  }, [item, map]);
  return null;
}

/** Fits the map to the pins once when results first arrive. */
function FitOnce({ items }: { items: CardItem[] }) {
  const map = useMap();
  const key = items.length;
  useEffect(() => {
    const pts = items.filter((i) => i.lat != null && i.lon != null).map((i) => [i.lat!, i.lon!] as [number, number]);
    if (pts.length > 1) map.fitBounds(pts as LatLngBoundsExpression, { padding: [60, 60], maxZoom: 15 });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key > 0]);
  return null;
}

interface Props {
  items: CardItem[];
  selectedId: string | null;
  hoveredId: string | null;
  onSelect: (id: string | null) => void;
}

export default function BakeoffMap({ items, selectedId, hoveredId, onSelect }: Props) {
  const pinned = useMemo(() => items.filter((i) => i.lat != null && i.lon != null), [items]);
  const selected = useMemo(() => items.find((i) => i.id === selectedId) ?? null, [items, selectedId]);

  return (
    <MapContainer center={SG_CENTER} zoom={12} zoomControl={false}
      className="h-full w-full" style={{ background: "#e8edf0" }}>
      <TileLayer url={GREY_TILES} />
      <FitOnce items={pinned} />
      <Recenter item={selected} />
      {pinned.map((it) => {
        const state = it.id === selectedId ? "selected" : it.id === hoveredId ? "hover" : "";
        return (
          <Marker key={it.id} position={[it.lat!, it.lon!]} icon={makeIcon(it, state)}
            eventHandlers={{ click: () => onSelect(it.id === selectedId ? null : it.id) }} />
        );
      })}
    </MapContainer>
  );
}
