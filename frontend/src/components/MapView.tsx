import { Fragment, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";
import { Bus } from "lucide-react";
import { Circle, CircleMarker, MapContainer, Marker, Pane, Polyline, Popup, TileLayer, Tooltip, useMap, useMapEvents } from "react-leaflet";
import { divIcon, type LatLngBoundsExpression } from "leaflet";
import useSupercluster from "use-supercluster";
import type { BlockSummary, DirectTransitDestination } from "../types";
import { ACCESS_COLORS, formatDistance, formatPsf, formatSGD, mrtAccessClass } from "../lib/format";
import { getBusStopReach, getReferenceLayer } from "../lib/api";
import type { BusReachResponse } from "../lib/api";
import { distanceMetres } from "../lib/geo";

const ONEMAP_TILES =
  "https://www.onemap.gov.sg/maps/tiles/Default/{z}/{x}/{y}.png";

// Max pan bounds — keeps user inside Singapore region
const SG_BOUNDS: LatLngBoundsExpression = [
  [1.1304, 103.6005], // SW corner
  [1.4784, 104.0120], // NE corner
];


const SHORTLIST_COLOR = "#7c3aed";
const SELECTED_COLOR = "#dc2626";
const BUS_COLORS = ["#2563eb", "#7c3aed", "#db2777", "#ea580c", "#059669", "#0891b2"];
const MRT_COLORS: Record<string, string> = {
  EW: "#009645",
  NS: "#d42e12",
  NE: "#9900aa",
  CC: "#fa9e0d",
  DT: "#005ec4",
  TE: "#9d5b25",
};

const LEGEND_ITEMS: { label: string; color: string }[] = [
  { label: "≤400m to MRT", color: ACCESS_COLORS.good },
  { label: "≤1km to MRT", color: ACCESS_COLORS.ok },
  { label: ">1km to MRT", color: ACCESS_COLORS.far },
  { label: "Unknown", color: ACCESS_COLORS.unknown },
    { label: "AI shortlist", color: SHORTLIST_COLOR },

];

// ── Clustering ────────────────────────────────────────────────────────────────

type BlockFeature = GeoJSON.Feature<GeoJSON.Point, BlockSummary & { cluster: false }>;

function ClusteredBlocks({
  blocks,
  shortlistIds,
  selectedBlockId,
  onSelectBlock,
}: {
  blocks: BlockSummary[];
  shortlistIds: Set<number>;
  selectedBlockId?: number | null;
  onSelectBlock?: (id: number) => void;
}) {
  const map = useMap();
  const [bounds, setBounds] = useState<[number, number, number, number]>([103.6, 1.13, 104.01, 1.48]);
  const [zoom, setZoom] = useState(map.getZoom());

  useEffect(() => {
    const update = () => {
      const b = map.getBounds();
      setBounds([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]);
      setZoom(map.getZoom());
    };
    update();
    map.on("moveend zoomend", update);
    return () => { map.off("moveend zoomend", update); };
  }, [map]);

  const points = useMemo<BlockFeature[]>(
    () =>
      blocks.map((b) => ({
        type: "Feature",
        properties: { ...b, cluster: false as const },
        geometry: { type: "Point", coordinates: [b.lon, b.lat] },
      })),
    [blocks],
  );

  const { clusters, supercluster } = useSupercluster({
    points,
    bounds,
    zoom,
    options: { radius: 60, maxZoom: 16, minPoints: 3 },
  });

  return (
    <>
      {clusters.map((cluster) => {
        const [lon, lat] = cluster.geometry.coordinates;
        const { cluster: isCluster, cluster_id, point_count } = cluster.properties as {
          cluster: boolean; cluster_id?: number; point_count?: number;
        };

        // ── Cluster bubble ───────────────────────────────────────────────
        if (isCluster && cluster_id != null && point_count != null) {
          const radius = Math.min(14 + Math.sqrt(point_count) * 1.8, 44);
          return (
            <CircleMarker
              key={`cluster-${cluster_id}`}
              center={[lat, lon]}
              radius={radius}
              pathOptions={{
                color: "#1e40af",
                fillColor: "#3b82f6",
                fillOpacity: 0.82,
                weight: 2,
              }}
              eventHandlers={{
                click: () => {
                  const expansionZoom = Math.min(
                    supercluster!.getClusterExpansionZoom(cluster_id),
                    18,
                  );
                  map.flyTo([lat, lon], expansionZoom, { animate: true, duration: 0.5 });
                },
              }}
            >
              <Tooltip
                permanent
                direction="center"
                className="cluster-label"
                opacity={1}
              >
                <span style={{ fontWeight: 700, fontSize: radius > 24 ? 13 : 11, color: "#fff" }}>
                  {point_count > 999 ? `${Math.round(point_count / 100) / 10}k` : point_count}
                </span>
              </Tooltip>
            </CircleMarker>
          );
        }

        // ── Individual block marker ───────────────────────────────────────
        const b = cluster.properties as BlockSummary;
        const isSelected = b.block_id === selectedBlockId;
        const isShortlisted = shortlistIds.has(b.block_id);
        const cls = mrtAccessClass(b.nearest_mrt_distance_m);
        const color = isSelected ? SELECTED_COLOR : isShortlisted ? SHORTLIST_COLOR : ACCESS_COLORS[cls];
        const radius = isSelected ? 11 : isShortlisted ? 9 : 7;

        return (
          <CircleMarker
            key={b.block_id}
            center={[lat, lon]}
            radius={radius}
            pathOptions={{
              color,
              fillColor: color,
              fillOpacity: isSelected ? 0.95 : isShortlisted ? 0.85 : 0.75,
              weight: isSelected || isShortlisted ? 2.5 : 1.5,
            }}
            eventHandlers={{ click: () => onSelectBlock?.(b.block_id) }}
          >
            <Popup>
              <div className="text-sm min-w-[180px]">
                <div className="font-semibold">Blk {b.block_number} {b.street_name}</div>
                <div className="text-gray-500 text-xs mb-2">{b.town}</div>
                <div className="space-y-1 text-xs">
                  <div className="flex justify-between gap-4">
                    <span className="text-gray-400">Median price</span>
                    <span className="font-medium">{formatSGD(b.median_price)}</span>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="text-gray-400">Median PSF</span>
                    <span className="font-medium">{formatPsf(b.median_psf)}</span>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="text-gray-400">MRT distance</span>
                    <span className="font-medium">{formatDistance(b.nearest_mrt_distance_m)}</span>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="text-gray-400">Schools (1km)</span>
                    <span className="font-medium">{b.schools_within_1km ?? "—"}</span>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="text-gray-400">Transactions</span>
                    <span className="font-medium">{b.txn_count}</span>
                  </div>
                </div>
                {b.transit_matches?.map((match) => (
                  <div key={match.destination} className="mt-2 rounded bg-blue-50 p-2 text-xs text-blue-900">
                    <div className="font-semibold">Direct to {match.destination}</div>
                    {match.options.map((option) => (
                      <div key={`${option.mode}-${option.service}`} className="mt-1">
                        {option.mode.toUpperCase()} {option.service}: walk {Math.ceil(option.origin_walk_m / 80)} min,
                        then walk {Math.ceil(option.destination_walk_m / 80)} min
                      </div>
                    ))}
                  </div>
                ))}
                {isShortlisted && (
                  <div className="mt-2 rounded bg-violet-50 px-2 py-1 text-xs text-violet-700 font-medium">
                    ✦ HomeOS shortlisted
                  </div>
                )}
                <p className="mt-2 text-xs text-gray-400 italic">Click to open detail panel →</p>
              </div>
            </Popup>
          </CircleMarker>
        );
      })}
    </>
  );
}

// Centre of Singapore's main HDB belt
const SG_CENTER: [number, number] = [1.352, 103.820];

export interface MapViewState {
  center: [number, number];
  zoom: number;
}

/** Keeps Leaflet sized correctly when surrounding panels open or close. */
function MapResizer() {
  const map = useMap();
  useLayoutEffect(() => {
    const container = map.getContainer();
    let frame = 0;
    const syncSize = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        map.invalidateSize({ animate: false, pan: false });
      });
    };
    const handleWindowResize = () => syncSize();

    map.invalidateSize({ animate: false, pan: false });
    syncSize();

    const observer = new ResizeObserver(() => syncSize());
    observer.observe(container);
    window.addEventListener("resize", handleWindowResize);

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener("resize", handleWindowResize);
    };
  }, [map]);
  return null;
}

function BusRouteFitter({ reach, activeService }: {
  reach: BusReachResponse | undefined;
  activeService: string | null;
}) {
  const map = useMap();
  useEffect(() => {
    if (!reach) return;
    const services = activeService
      ? reach.services.filter(
          (service) => `${service.service_no}-${service.direction}` === activeService,
        )
      : reach.services;
    const points = services.flatMap((service) =>
      service.stops.map((stop) => [stop.lat, stop.lon] as [number, number]),
    );
    if (points.length > 1) {
      map.fitBounds(points, { padding: [45, 45], maxZoom: 14, animate: true });
    }
  }, [activeService, map, reach]);
  return null;
}

function MapViewTracker({ onViewChange }: { onViewChange?: (view: MapViewState) => void }) {
  useMapEvents({
    moveend(event) {
      const center = event.target.getCenter();
      onViewChange?.({ center: [center.lat, center.lng], zoom: event.target.getZoom() });
    },
  });
  return null;
}

function RecommendationFitter({
  blocks,
  rankedIds,
  enabled,
  onFitted,
}: {
  blocks: BlockSummary[];
  rankedIds: number[];
  enabled: boolean;
  onFitted?: () => void;
}) {
  const map = useMap();
  useEffect(() => {
    if (!enabled || rankedIds.length === 0) return;
    const ids = new Set(rankedIds);
    const points = blocks
      .filter((block) => ids.has(block.block_id))
      .map((block) => [block.lat, block.lon] as [number, number]);
    if (points.length === 1) map.flyTo(points[0], 15, { animate: true, duration: 0.5 });
    if (points.length > 1) map.fitBounds(points, { padding: [60, 60], maxZoom: 15, animate: true });
    if (points.length > 0) onFitted?.();
  }, [blocks, enabled, map, onFitted, rankedIds]);
  return null;
}

function RecommendedBlocks({
  blocks,
  rankedIds,
  selectedBlockId,
  onSelectBlock,
}: {
  blocks: BlockSummary[];
  rankedIds: number[];
  selectedBlockId?: number | null;
  onSelectBlock?: (id: number) => void;
}) {
  const rankById = useMemo(
    () => new Map(rankedIds.map((blockId, index) => [blockId, index + 1])),
    [rankedIds],
  );
  const recommendations = useMemo(
    () => blocks.filter((block) => rankById.has(block.block_id)),
    [blocks, rankById],
  );

  return (
    <Pane name="recommendations" style={{ zIndex: 600 }}>
      {recommendations.map((block) => {
        const rank = rankById.get(block.block_id)!;
        const isSelected = block.block_id === selectedBlockId;
        const icon = divIcon({
          className: "recommendation-marker-wrapper",
          html: `<div class="recommendation-marker${isSelected ? " recommendation-marker-selected" : ""}">${rank}</div>`,
          iconSize: [30, 30],
          iconAnchor: [15, 15],
          popupAnchor: [0, -16],
        });
        return (
          <Marker
            key={block.block_id}
            position={[block.lat, block.lon]}
            pane="recommendations"
            icon={icon}
            eventHandlers={{ click: () => onSelectBlock?.(block.block_id) }}
          >
            <Popup>
              <div className="min-w-[180px] text-sm">
                <div className="font-semibold">#{rank} Blk {block.block_number} {block.street_name}</div>
                <div className="text-xs text-gray-500">{block.town}</div>
              </div>
            </Popup>
          </Marker>
        );
      })}
    </Pane>
  );
}

function DestinationMarkers({ destinations }: { destinations: DirectTransitDestination[] }) {
  return (
    <Pane name="destinations" style={{ zIndex: 650 }}>
      {destinations.map((destination, index) => {
        const icon = divIcon({
          className: "destination-marker-wrapper",
          html: `<div class="destination-marker"><span>${index + 1}</span></div>`,
          iconSize: [34, 42],
          iconAnchor: [17, 42],
          popupAnchor: [0, -38],
        });
        return (
          <Marker
            key={`${destination.name}-${destination.lat}-${destination.lon}-${index}`}
            position={[destination.lat, destination.lon]}
            pane="destinations"
            icon={icon}
          >
            <Tooltip direction="top" offset={[0, -36]} opacity={0.95}>
              <strong>{destination.name}</strong>
              {destination.address && <><br />{destination.address}</>}
            </Tooltip>
            <Popup>
              <div className="text-sm">
                <div className="font-semibold">Destination {index + 1}</div>
                <div className="mt-1">{destination.name}</div>
                {destination.address && (
                  <div className="mt-1 text-xs text-gray-500">{destination.address}</div>
                )}
              </div>
            </Popup>
          </Marker>
        );
      })}
    </Pane>
  );
}

function NearbyBusRouteFitter({
  selectedBlock,
  routes,
  loading,
}: {
  selectedBlock: BlockSummary | null;
  routes: (BusReachResponse["services"][number] & { originCode: string })[];
  loading: boolean;
}) {
  const map = useMap();
  const fittedBlockId = useRef<number | null>(null);
  useEffect(() => {
    if (!selectedBlock) {
      fittedBlockId.current = null;
      return;
    }
    if (loading || routes.length === 0 || fittedBlockId.current === selectedBlock.block_id) return;
    const points = [
      [selectedBlock.lat, selectedBlock.lon] as [number, number],
      ...routes.flatMap((service) =>
        service.stops.map((stop) => [stop.lat, stop.lon] as [number, number]),
      ),
    ];
    fittedBlockId.current = selectedBlock.block_id;
    map.fitBounds(points, { padding: [45, 45], maxZoom: 14, animate: true });
  }, [loading, map, routes, selectedBlock]);
  return null;
}

function SelectionViewRestorer({ selectedBlock }: { selectedBlock: BlockSummary | null }) {
  const map = useMap();
  const previousBlockId = useRef<number | null>(null);
  const propertyView = useRef<{ center: [number, number]; zoom: number } | null>(null);

  useEffect(() => {
    if (selectedBlock && previousBlockId.current == null) {
      propertyView.current = {
        center: [selectedBlock.lat, selectedBlock.lon],
        zoom: map.getZoom(),
      };
    } else if (!selectedBlock && previousBlockId.current != null && propertyView.current) {
      map.flyTo(propertyView.current.center, propertyView.current.zoom, {
        animate: true,
        duration: 0.5,
      });
      propertyView.current = null;
    }
    previousBlockId.current = selectedBlock?.block_id ?? null;
  }, [map, selectedBlock]);

  return null;
}

interface Props {
  blocks: BlockSummary[];
  shortlistIds?: number[];
  selectedBlockId?: number | null;
  onSelectBlock?: (blockId: number) => void;
  profileText?: string; // reserved for future case-file integration
  nearbyBusRadiusM?: number;
  onNearbyBusRadiusChange?: (radiusM: number) => void;
  hasSelectedProperty?: boolean;
  recommendationsOnly?: boolean;
  initialView?: MapViewState;
  onViewChange?: (view: MapViewState) => void;
  fitRecommendations?: boolean;
  onRecommendationsFitted?: () => void;
  destinations?: DirectTransitDestination[];
}

export default function MapView({
  blocks,
  shortlistIds = [],
  selectedBlockId,
  onSelectBlock,
  nearbyBusRadiusM = 0,
  onNearbyBusRadiusChange,
  hasSelectedProperty = false,
  recommendationsOnly = false,
  initialView = { center: SG_CENTER, zoom: 12 },
  onViewChange,
  fitRecommendations = false,
  onRecommendationsFitted,
  destinations = [],
}: Props) {
  const showNearbyBusRoutes = nearbyBusRadiusM > 0;
  const shortlistSet = useMemo(() => new Set(shortlistIds), [shortlistIds]);
  const [busMode, setBusMode] = useState(false);
  const [selectedBusStop, setSelectedBusStop] = useState<string | null>(null);
  const [activeBusService, setActiveBusService] = useState<string | null>(null);

  useEffect(() => {
    if (selectedBusStop == null) return;

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopPropagation();
      setSelectedBusStop(null);
      setActiveBusService(null);
    };

    document.addEventListener("keydown", handleEscape, true);
    return () => document.removeEventListener("keydown", handleEscape, true);
  }, [selectedBusStop]);
  const selectedBlock = useMemo(
    () => blocks.find((block) => block.block_id === selectedBlockId) ?? null,
    [blocks, selectedBlockId],
  );
  const busStops = useQuery({
    queryKey: ["reference", "bus_stops"],
    queryFn: () => getReferenceLayer("bus_stops"),
    enabled: busMode || (showNearbyBusRoutes && selectedBlock != null),
  });
  const mrtStations = useQuery({
    queryKey: ["reference", "mrt"],
    queryFn: () => getReferenceLayer("mrt"),
    enabled: showNearbyBusRoutes && selectedBlock != null,
  });
  const busReach = useQuery({
    queryKey: ["bus-reach", selectedBusStop],
    queryFn: () => getBusStopReach(selectedBusStop!),
    enabled: busMode && selectedBusStop != null,
  });
  const displayedServices = busReach.data?.services.filter((service) =>
    activeBusService == null
      || `${service.service_no}-${service.direction}` === activeBusService
  ) ?? [];
  const nearbyStops = useMemo(() => {
    if (!showNearbyBusRoutes || !selectedBlock || !busStops.data) return [];
    return busStops.data.features.flatMap((feature) => {
      const [lon, lat] = feature.geometry.coordinates;
      const distance = distanceMetres(selectedBlock, { lat, lon });
      if (distance > nearbyBusRadiusM) return [];
      return [{
        code: String(feature.properties.code ?? ""),
        description: String(feature.properties.description ?? "Bus stop"),
        lat,
        lon,
        distance,
      }];
    }).filter((stop) => stop.code).sort((a, b) => a.distance - b.distance);
  }, [busStops.data, nearbyBusRadiusM, selectedBlock, showNearbyBusRoutes]);
  const mrtLines = useMemo(() => {
    const lines = new Map<string, {
      stationId: number;
      name: string;
      line: string;
      lat: number;
      lon: number;
    }[]>();
    for (const feature of mrtStations.data?.features ?? []) {
      const stationId = Number(feature.properties.station_id);
      const line = String(feature.properties.line_name ?? "");
      if (!Number.isFinite(stationId) || !line) continue;
      const [lon, lat] = feature.geometry.coordinates;
      const stations = lines.get(line) ?? [];
      stations.push({ stationId, name: String(feature.properties.name ?? "MRT station"), line, lat, lon });
      lines.set(line, stations);
    }
    for (const stations of lines.values()) {
      stations.sort((a, b) => a.stationId - b.stationId);
    }
    return lines;
  }, [mrtStations.data]);
  const nearbyMrtStations = useMemo(() => {
    if (!showNearbyBusRoutes || !selectedBlock) return [];
    return [...mrtLines.values()].flatMap((stations) => stations).filter((station) =>
      distanceMetres(selectedBlock, station) <= nearbyBusRadiusM
    ).map((station) => ({
      ...station,
      distance: distanceMetres(selectedBlock, station),
    })).sort((a, b) => a.distance - b.distance);
  }, [mrtLines, nearbyBusRadiusM, selectedBlock, showNearbyBusRoutes]);
  const nearbyMrtLineNames = useMemo(
    () => [...new Set(nearbyMrtStations.map((station) => station.line))],
    [nearbyMrtStations],
  );
  const nearbyReachQueries = useQueries({
    queries: nearbyStops.map((stop) => ({
      queryKey: ["bus-reach", stop.code],
      queryFn: () => getBusStopReach(stop.code),
      enabled: showNearbyBusRoutes && !busMode,
      staleTime: 5 * 60 * 1000,
    })),
  });
  const nearbyRoutes = nearbyReachQueries.flatMap((query, stopIndex) =>
    (query.data?.services ?? []).map((service) => ({
      ...service,
      originCode: nearbyStops[stopIndex].code,
    })),
  );
  const nearbyRoutesLoading = nearbyReachQueries.some((query) => query.isLoading);
  const nearbyRoutesError = nearbyReachQueries.some((query) => query.isError);
  const nearbyRouteFocus = !busMode && showNearbyBusRoutes && selectedBlock != null;

  return (
    <div className="absolute inset-0 overflow-hidden bg-[#aacbdf]">
      <MapContainer
        center={initialView.center}
        zoom={initialView.zoom}
        minZoom={11}
        maxZoom={18}
        maxBounds={SG_BOUNDS}
        maxBoundsViscosity={1.0}
        preferCanvas
        className="h-full w-full"
      >
        <MapResizer />
        <MapViewTracker onViewChange={onViewChange} />
        <RecommendationFitter
          blocks={blocks}
          rankedIds={shortlistIds}
          enabled={fitRecommendations}
          onFitted={onRecommendationsFitted}
        />
        <SelectionViewRestorer selectedBlock={selectedBlock} />
        <BusRouteFitter reach={busReach.data} activeService={activeBusService} />
        {!busMode && showNearbyBusRoutes && (
          <NearbyBusRouteFitter
            selectedBlock={selectedBlock}
            routes={nearbyRoutes}
            loading={nearbyRoutesLoading}
          />
        )}

        <TileLayer
          url={ONEMAP_TILES}
          attribution='&copy; <a href="https://www.onemap.gov.sg/">OneMap</a>'
          minZoom={11}
          maxZoom={18}
          keepBuffer={4}
        />

        {destinations.length > 0 && <DestinationMarkers destinations={destinations} />}

        {!busMode && !nearbyRouteFocus && !recommendationsOnly && (
          <ClusteredBlocks
            blocks={blocks}
            shortlistIds={shortlistSet}
            selectedBlockId={selectedBlockId}
            onSelectBlock={onSelectBlock}
          />
        )}

        {!busMode && !nearbyRouteFocus && recommendationsOnly && shortlistIds.length > 0 && (
          <RecommendedBlocks
            blocks={blocks}
            rankedIds={shortlistIds}
            selectedBlockId={selectedBlockId}
            onSelectBlock={onSelectBlock}
          />
        )}

        {(busMode || nearbyRouteFocus) && (
        <Pane
          key={busMode ? "bus-routes-interactive" : `nearby-routes-${selectedBlockId}`}
          name={busMode ? "bus-routes" : "nearby-bus-routes"}
          style={{ zIndex: 610, pointerEvents: busMode ? "auto" : "none" }}
        >
          {busMode && displayedServices.map((service, index) => {
            const positions = service.stops.map((stop) => [stop.lat, stop.lon] as [number, number]);
            const color = BUS_COLORS[index % BUS_COLORS.length];
            return (
              <Fragment key={`${service.service_no}-${service.direction}`}>
                <Polyline
                  positions={positions}
                  pathOptions={{ pane: "bus-routes", color: "#ffffff", weight: 9, opacity: 0.9 }}
                />
                <Polyline
                  positions={positions}
                  pathOptions={{ pane: "bus-routes", color, weight: 6, opacity: 0.95 }}
                >
                  <Tooltip sticky opacity={0.95}>
                    Bus {service.service_no}, direction {service.direction}
                  </Tooltip>
                  <Popup>
                    Bus {service.service_no}, direction {service.direction}
                  </Popup>
                </Polyline>
              </Fragment>
            );
          })}
          {nearbyRouteFocus && nearbyRoutes.map((service, index) => {
            const positions = service.stops.map((stop) => [stop.lat, stop.lon] as [number, number]);
            const color = BUS_COLORS[index % BUS_COLORS.length];
            return (
              <Fragment key={`nearby-${service.originCode}-${service.service_no}-${service.direction}`}>
                <Polyline
                  positions={positions}
                  interactive={false}
                  pathOptions={{ pane: "nearby-bus-routes", color: "#ffffff", weight: 7, opacity: 0.75 }}
                />
                <Polyline
                  positions={positions}
                  interactive={false}
                  pathOptions={{ pane: "nearby-bus-routes", color, weight: 4, opacity: 0.9 }}
                />
              </Fragment>
            );
          })}
          {nearbyRouteFocus && nearbyMrtLineNames.map((line) => {
            const stations = mrtLines.get(line) ?? [];
            const positions = stations.map((station) => [station.lat, station.lon] as [number, number]);
            const color = MRT_COLORS[line] ?? "#334155";
            return (
              <Fragment key={`nearby-mrt-${line}`}>
                <Polyline
                  positions={positions}
                  interactive={false}
                  pathOptions={{ pane: "nearby-bus-routes", color: "#ffffff", weight: 9, opacity: 0.8 }}
                />
                <Polyline
                  positions={positions}
                  interactive={false}
                  pathOptions={{ pane: "nearby-bus-routes", color, weight: 6, opacity: 0.95 }}
                />
              </Fragment>
            );
          })}
        </Pane>
        )}

        {!busMode && showNearbyBusRoutes && selectedBlock && (
          <Pane
            key={`nearby-origins-${selectedBlock.block_id}`}
            name="nearby-bus-origins"
            style={{ zIndex: 625, pointerEvents: "none" }}
          >
            <Circle
              center={[selectedBlock.lat, selectedBlock.lon]}
              radius={nearbyBusRadiusM}
              interactive={false}
              pathOptions={{ color: "#2563eb", fillColor: "#60a5fa", fillOpacity: 0.08, dashArray: "6 5" }}
            />
            <CircleMarker
              center={[selectedBlock.lat, selectedBlock.lon]}
              radius={11}
              interactive={false}
              pathOptions={{
                pane: "nearby-bus-origins",
                color: "#7f1d1d",
                fillColor: SELECTED_COLOR,
                fillOpacity: 1,
                weight: 3,
              }}
            >
              <Tooltip direction="top" opacity={0.95}>
                Blk {selectedBlock.block_number} {selectedBlock.street_name}
              </Tooltip>
            </CircleMarker>
            {nearbyStops.map((stop) => (
              <CircleMarker
                key={`nearby-origin-${stop.code}`}
                center={[stop.lat, stop.lon]}
                radius={8}
                interactive={false}
                pathOptions={{ pane: "nearby-bus-origins", color: "#1e3a8a", fillColor: "#facc15", fillOpacity: 0.95, weight: 2 }}
              />
            ))}
            {nearbyMrtStations.map((station) => (
              <CircleMarker
                key={`nearby-mrt-origin-${station.stationId}`}
                center={[station.lat, station.lon]}
                radius={10}
                interactive={false}
                pathOptions={{
                  pane: "nearby-bus-origins",
                  color: MRT_COLORS[station.line] ?? "#334155",
                  fillColor: "#ffffff",
                  fillOpacity: 1,
                  weight: 4,
                }}
              />
            ))}
          </Pane>
        )}

        {busMode && (
        <Pane name="bus-stops" style={{ zIndex: 620 }}>
          {busMode && busStops.data?.features
            .filter((feature) => {
              if (selectedBusStop == null) return true;
              return String(feature.properties.code ?? "") === selectedBusStop;
            })
            .map((feature) => {
            const code = String(feature.properties.code ?? "");
            const description = String(feature.properties.description ?? `Bus Stop ${code}`);
            const [lon, lat] = feature.geometry.coordinates;
            const isOrigin = code === selectedBusStop;
            return (
              <CircleMarker
                key={`bus-${code}`}
                center={[lat, lon]}
                radius={isOrigin ? 10 : 5}
                pathOptions={{
                  pane: "bus-stops",
                  color: isOrigin ? "#dc2626" : "#0f172a",
                  fillColor: isOrigin ? "#dc2626" : "#facc15",
                  fillOpacity: isOrigin ? 0.95 : 0.85,
                  weight: isOrigin ? 3 : 1.5,
                }}
                eventHandlers={{
                  click: (event) => {
                    event.originalEvent.stopPropagation();
                    setSelectedBusStop((current) => current === code ? null : code);
                    setActiveBusService(null);
                  },
                }}
              >
                <Tooltip direction="top" offset={[0, -5]} opacity={0.95}>
                  {description} ({code})
                </Tooltip>
                <Popup>
                  <div className="min-w-[150px] text-sm">
                    <div className="font-semibold">{description}</div>
                    <div className="text-xs text-gray-500">Stop {code}</div>
                    <div className="mt-1 text-xs text-blue-700">
                      {isOrigin ? "Click again to show all bus stops" : "Click to show direct bus reach"}
                    </div>
                  </div>
                </Popup>
              </CircleMarker>
            );
          })}
        </Pane>
        )}
      </MapContainer>

      <button
        type="button"
        onClick={() => {
          setBusMode((enabled) => !enabled);
          setSelectedBusStop(null);
          setActiveBusService(null);
        }}
        className={`absolute right-3 top-3 z-[1000] flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium shadow-md ${
          busMode ? "border-blue-600 bg-blue-600 text-white" : "border-border bg-card text-foreground"
        }`}
      >
        <Bus className="h-4 w-4" />
        Bus Reach
      </button>

      {busMode && (
        <div className="absolute right-3 top-14 z-[1000] w-72 rounded-xl border border-border bg-card/95 p-3 shadow-md backdrop-blur-sm">
          {!selectedBusStop && <p className="text-sm">Select a bus stop to see every directly reachable downstream stop.</p>}
          {busStops.isLoading && <p className="text-sm">Loading bus stops...</p>}
          {busStops.data && !selectedBusStop && (
            <p className="mt-2 text-xs text-muted-foreground">
              {busStops.data.features.length.toLocaleString()} stops loaded. Yellow circles are clickable; zoom in for easier selection.
            </p>
          )}
          {selectedBusStop && !busReach.data && (
            <p className="font-semibold">Selected stop {selectedBusStop}</p>
          )}
          {busReach.isLoading && <p className="text-sm">Loading route reach...</p>}
          {busReach.isError && (
            <p className="text-sm text-destructive">
              Bus routes are not loaded yet. Configure the LTA DataMall key and sync the network.
            </p>
          )}
          {busReach.data && (
            <>
              <p className="font-semibold">{busReach.data.origin.description}</p>
              <p className="text-xs text-muted-foreground">Stop {busReach.data.origin.bus_stop_code}</p>
              <p className="mt-2 text-sm">
                {busReach.data.service_count} routes reach {busReach.data.reachable_stop_count} downstream stops.
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                Only route lines are shown. Click the red origin stop again to restore all bus stops.
              </p>
              <div className="mt-2 flex flex-wrap gap-1">
                <button
                  type="button"
                  onClick={() => setActiveBusService(null)}
                  className={`rounded border px-2 py-1 text-xs font-semibold ${
                    activeBusService == null
                      ? "border-slate-900 bg-slate-900 text-white"
                      : "border-border bg-background text-foreground"
                  }`}
                >
                  All routes
                </button>
                {busReach.data.services.map((service, index) => (
                  <button
                    type="button"
                    key={`${service.service_no}-${service.direction}`}
                    onClick={() => setActiveBusService(`${service.service_no}-${service.direction}`)}
                    className={`rounded border-2 px-2 py-1 text-xs font-semibold text-white ${
                      activeBusService === `${service.service_no}-${service.direction}`
                        ? "border-slate-950"
                        : "border-transparent"
                    }`}
                    style={{ backgroundColor: BUS_COLORS[index % BUS_COLORS.length] }}
                  >
                    {service.service_no} D{service.direction}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {!busMode && showNearbyBusRoutes && (
        <div className="absolute right-3 top-14 z-[1000] w-72 rounded-xl border border-border bg-card/95 p-3 shadow-md backdrop-blur-sm">
          {!selectedBlock && <p className="text-sm">Select a property to show transit routes within {nearbyBusRadiusM} m.</p>}
          {selectedBlock && (busStops.isLoading || mrtStations.isLoading) && <p className="text-sm">Finding nearby transit...</p>}
          {selectedBlock && busStops.data && mrtStations.data && nearbyStops.length === 0 && nearbyMrtStations.length === 0 && (
            <p className="text-sm">No bus stops or MRT stations were found within {nearbyBusRadiusM} m of this property.</p>
          )}
          {selectedBlock && (nearbyStops.length > 0 || nearbyMrtStations.length > 0) && (
            <>
              <p className="font-semibold">Transit within {nearbyBusRadiusM} m</p>
              <p className="mt-1 text-sm">
                {nearbyStops.length} nearby {nearbyStops.length === 1 ? "stop" : "stops"}
                {nearbyRoutes.length > 0 ? `, ${nearbyRoutes.length} bus routes` : ""}
                {nearbyMrtStations.length > 0 ? `, ${nearbyMrtStations.length} MRT station records` : ""}.
              </p>
              {nearbyRoutesLoading && <p className="mt-1 text-xs text-muted-foreground">Loading route lines...</p>}
              {nearbyRoutesError && <p className="mt-1 text-xs text-destructive">Some route data could not be loaded.</p>}
              <div className="mt-2 space-y-1">
                {nearbyStops.map((stop) => (
                  <p key={`nearby-summary-${stop.code}`} className="text-xs text-muted-foreground">
                    {stop.code}: {stop.description} ({Math.round(stop.distance)} m)
                  </p>
                ))}
                {nearbyMrtStations.map((station) => (
                  <p key={`nearby-mrt-summary-${station.stationId}`} className="text-xs font-medium" style={{ color: MRT_COLORS[station.line] ?? "#334155" }}>
                    {station.line}: {station.name} ({Math.round(station.distance)} m)
                  </p>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {!busMode && !nearbyRouteFocus && <div className="absolute bottom-6 right-3 z-[1000] w-56 rounded-xl border border-border bg-card/90 p-3 shadow-md backdrop-blur-sm">
        {/* Display controls */}
        {onNearbyBusRadiusChange && (
          <div className="mb-3 border-b border-border pb-3">
            <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Display
            </p>
            <label htmlFor="map-nearby-radius" className="block text-xs font-medium text-foreground">
              Nearby transit radius
            </label>
            <div className="mt-1 flex items-center gap-2">
              <input
                id="map-nearby-radius"
                type="number"
                min={0}
                max={2000}
                step={50}
                value={nearbyBusRadiusM}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  onNearbyBusRadiusChange(Number.isFinite(v) ? Math.min(2000, Math.max(0, v)) : 0);
                }}
                className="h-7 w-20 rounded border border-input bg-background px-2 text-xs"
              />
              <span className="text-[11px] text-muted-foreground">metres</span>
            </div>
            <p className="mt-1 text-[10px] leading-tight text-muted-foreground">
              {hasSelectedProperty
                ? "Bus & MRT routes near the selected property. 0 hides it."
                : "Select a property to show its nearby transit routes."}
            </p>
          </div>
        )}
        <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          MRT Access
        </p>
        <div className="space-y-1.5">
          {LEGEND_ITEMS.map(({ label, color }) => (
            <div key={label} className="flex items-center gap-2">
              <span
                className="h-3 w-3 shrink-0 rounded-full"
                style={{ backgroundColor: color }}
              />
              <span className="text-xs text-foreground">{label}</span>
            </div>
          ))}
        </div>
      </div>}
    </div>
  );
}
