import { Fragment, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bus } from "lucide-react";
import { CircleMarker, MapContainer, Pane, Polyline, Popup, TileLayer, Tooltip, useMap } from "react-leaflet";
import type { LatLngBoundsExpression } from "leaflet";
import useSupercluster from "use-supercluster";
import type { BlockSummary } from "../types";
import { ACCESS_COLORS, formatDistance, formatPsf, formatSGD, mrtAccessClass } from "../lib/format";
import { getBusStopReach, getReferenceLayer } from "../lib/api";
import type { BusReachResponse } from "../lib/api";

const ONEMAP_TILES =
  "https://www.onemap.gov.sg/maps/tiles/Default/{z}/{x}/{y}.png";

// Bounds around Singapore — map is fitted to these on load and pan is locked to them
const SG_BOUNDS: LatLngBoundsExpression = [
  [1.1304, 103.6005], // SW corner
  [1.4784, 104.0120], // NE corner
];

const SHORTLIST_COLOR = "#7c3aed";
const SELECTED_COLOR = "#dc2626";
const BUS_COLORS = ["#2563eb", "#7c3aed", "#db2777", "#ea580c", "#059669", "#0891b2"];

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

/** Fits the map to Singapore bounds on mount so there are no empty tile edges. */
function MapInitializer() {
  const map = useMap();
  useEffect(() => {
    map.fitBounds(SG_BOUNDS, { padding: [0, 0], animate: false });
  }, [map]);
  return null;
}

/** Watches the map container with ResizeObserver and calls invalidateSize
 *  whenever it changes — handles sidebar open/close reliably. */
function MapResizer() {
  const map = useMap();
  useEffect(() => {
    const container = map.getContainer();
    const observer = new ResizeObserver(() => map.invalidateSize({ animate: false }));
    observer.observe(container);
    return () => observer.disconnect();
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

interface Props {
  blocks: BlockSummary[];
  shortlistIds?: number[];
  selectedBlockId?: number | null;
  onSelectBlock?: (blockId: number) => void;
  profileText?: string; // reserved for future case-file integration
}

export default function MapView({
  blocks,
  shortlistIds = [],
  selectedBlockId,
  onSelectBlock,
}: Props) {
  const shortlistSet = useMemo(() => new Set(shortlistIds), [shortlistIds]);
  const [busMode, setBusMode] = useState(false);
  const [selectedBusStop, setSelectedBusStop] = useState<string | null>(null);
  const [activeBusService, setActiveBusService] = useState<string | null>(null);
  const busStops = useQuery({
    queryKey: ["reference", "bus_stops"],
    queryFn: () => getReferenceLayer("bus_stops"),
    enabled: busMode,
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

  return (
    <div className="relative h-full w-full bg-[#e8e0d8]">
      <MapContainer
        bounds={SG_BOUNDS}
        boundsOptions={{ padding: [0, 0] }}
        minZoom={11}
        maxZoom={18}
        maxBounds={SG_BOUNDS}
        maxBoundsViscosity={1.0}
        preferCanvas
        className="h-full w-full"
      >
        <MapInitializer />
        <MapResizer />
        <BusRouteFitter reach={busReach.data} activeService={activeBusService} />

        <TileLayer
          url={ONEMAP_TILES}
          attribution='&copy; <a href="https://www.onemap.gov.sg/">OneMap</a>'
          minZoom={11}
          maxZoom={18}
          keepBuffer={4}
        />

        {!busMode && (
          <ClusteredBlocks
            blocks={blocks}
            shortlistIds={shortlistSet}
            selectedBlockId={selectedBlockId}
            onSelectBlock={onSelectBlock}
          />
        )}

        <Pane name="bus-routes" style={{ zIndex: 610 }}>
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
        </Pane>

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

      {!busMode && <div className="absolute bottom-6 right-3 z-[1000] rounded-xl border border-border bg-card/90 p-3 shadow-md backdrop-blur-sm">
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
