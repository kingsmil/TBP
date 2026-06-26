import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { X, Heart, GitCompareArrows, MapPin, TrendingUp, Train, GraduationCap, Tag } from "lucide-react";
import type { CardItem } from "./types";
import { propertyImageUrl, getAppreciation, getEstateAnalytics, getBlockListings } from "../../lib/api";
import PsfTrendChart from "../PsfTrendChart";
import ScoreBar from "./ScoreBar";

const sgd = (n?: number | null) => (n != null ? `$${Math.round(n).toLocaleString()}` : "—");
const clamp = (n: number) => Math.max(0, Math.min(100, n));

interface Props {
  item: CardItem;
  saved: boolean;
  comparing: boolean;
  onClose: () => void;
  onSave: () => void;
  onCompare: () => void;
}

function Spec({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-muted/50 p-2.5">
      <div className="truncate text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="truncate text-sm font-semibold">{value}</div>
    </div>
  );
}

function SubScore({ icon: Icon, label, score }: { icon: typeof Train; label: string; score: number }) {
  return (
    <div className="flex items-center gap-2">
      <Icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
      <span className="w-20 shrink-0 text-xs text-muted-foreground">{label}</span>
      <div className="flex-1"><ScoreBar score={Math.round(score)} /></div>
    </div>
  );
}

export default function DetailPanel({ item, saved, comparing, onClose, onSave, onCompare }: Props) {
  const [imgOk, setImgOk] = useState(true);
  const [imgLoaded, setImgLoaded] = useState(false);
  // Reset image state when the property changes so it never sticks on the old one.
  useEffect(() => { setImgOk(true); setImgLoaded(false); }, [item.id]);
  const b = item.block;
  const hasCoords = item.lat != null && item.lon != null;
  const canImage = imgOk && (b?.block_id != null || hasCoords);
  const imgUrl = propertyImageUrl({ blockId: b?.block_id, lat: item.lat, lon: item.lon });

  // Resale-only enrichment (real endpoints, on demand).
  const appr = useQuery({
    queryKey: ["bo-appr", b?.block_id],
    queryFn: () => getAppreciation(b!.block_id),
    enabled: !!b, staleTime: 6e5,
  });
  const estate = useQuery({
    queryKey: ["bo-estate", b?.planning_area_id],
    queryFn: () => getEstateAnalytics(b!.planning_area_id as number),
    enabled: !!b?.planning_area_id, staleTime: 6e5,
  });
  const listings = useQuery({
    queryKey: ["bo-listings", b?.block_id],
    queryFn: () => getBlockListings(b!.block_id),
    enabled: !!b, staleTime: 6e5,
  });

  const commute = b ? (b.nearest_mrt_distance_m == null ? 50 : clamp(100 - (b.nearest_mrt_distance_m / 1000) * 100)) : null;
  const lifestyle = b ? clamp((b.schools_within_1km ?? 0) * 33) : null;
  const cheapest = listings.data?.listings?.[0];

  return (
    <div className="bo-glass bo-spring-up pointer-events-auto fixed inset-x-0 bottom-0 z-[1200] flex max-h-[86vh] flex-col overflow-hidden rounded-t-2xl sm:inset-x-auto sm:right-3 sm:top-3 sm:bottom-3 sm:w-[380px] sm:max-h-none sm:rounded-2xl">
      {/* Image header */}
      <div className="relative h-44 shrink-0 overflow-hidden bg-gradient-to-br from-primary/25 via-primary/10 to-transparent">
        {canImage && (
          <img key={item.id} src={imgUrl} alt={item.title}
            onLoad={() => setImgLoaded(true)} onError={() => setImgOk(false)}
            className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-300 ${imgLoaded ? "opacity-100" : "opacity-0"}`} />
        )}
        {canImage && !imgLoaded && (
          <div className="absolute inset-0 animate-pulse bg-muted/50" />
        )}
        <div className="absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-black/55 to-transparent" />
        <button type="button" onClick={onClose}
          className="absolute right-2 top-2 flex h-8 w-8 items-center justify-center rounded-full bg-card/85 hover:bg-card">
          <X className="h-4 w-4" />
        </button>
        {item.badge && (
          <span className="absolute left-3 top-3 rounded-full bg-card/85 px-2 py-0.5 text-[11px] font-semibold">{item.badge}</span>
        )}
        <div className="absolute inset-x-3 bottom-2 flex items-end justify-between text-white">
          <div className="min-w-0">
            <h2 className="truncate text-base font-bold drop-shadow">{item.title}</h2>
            <p className="flex items-center gap-1 text-xs opacity-90"><MapPin className="h-3 w-3" />{item.subtitle}</p>
          </div>
        </div>
      </div>

      {/* Scroll body */}
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
        {/* Price + actions */}
        <div className="flex items-end justify-between">
          <div>
            <div className="text-2xl font-bold tabular-nums">{item.pinLabel && item.price == null ? item.metrics[2]?.value ?? "—" : sgd(item.price)}</div>
            <div className="text-[11px] text-muted-foreground">{item.priceLabel}{item.psf != null ? ` · $${item.psf}/sqft` : ""}</div>
          </div>
          <div className="flex gap-1.5">
            <button type="button" onClick={onSave}
              className={`flex h-9 w-9 items-center justify-center rounded-full border ${saved ? "border-primary bg-primary/10 text-primary" : "border-border hover:bg-muted"}`}>
              <Heart className={`h-4 w-4 ${saved ? "fill-current" : ""}`} />
            </button>
            <button type="button" onClick={onCompare}
              className={`flex h-9 w-9 items-center justify-center rounded-full border ${comparing ? "border-primary bg-primary/10 text-primary" : "border-border hover:bg-muted"}`}>
              <GitCompareArrows className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Match + sub-scores (resale) */}
        {item.score != null && (
          <div className="space-y-2 rounded-xl border border-border bg-card/60 p-3">
            <div className="flex items-center justify-between text-xs font-semibold"><span>Match</span><span className="text-muted-foreground">{item.score}/100</span></div>
            <ScoreBar score={item.score} gradient />
            {commute != null && lifestyle != null && (
              <div className="space-y-1.5 pt-1">
                <SubScore icon={Train} label="Commute" score={commute} />
                <SubScore icon={GraduationCap} label="Lifestyle" score={lifestyle} />
                {appr.data?.appreciation_score != null && (
                  <SubScore icon={TrendingUp} label="Appreciation" score={appr.data.appreciation_score} />
                )}
              </div>
            )}
          </div>
        )}

        {/* Specs */}
        <div>
          <div className="mb-2 text-xs font-semibold text-muted-foreground">Details</div>
          <div className="grid grid-cols-2 gap-2">
            {item.metrics.map((m) => <Spec key={m.label} label={m.label} value={m.value} />)}
            {b && <Spec label="Town" value={b.town} />}
            {b && <Spec label="Transactions" value={String(b.txn_count)} />}
            {appr.data?.risk_level && <Spec label="Risk" value={appr.data.risk_level} />}
          </div>
        </div>

        {/* Active listings (resale) */}
        {cheapest && (
          <div className="rounded-xl border border-border bg-card/60 p-3">
            <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold"><Tag className="h-3.5 w-3.5" /> On the market now</div>
            <p className="text-sm">
              <span className="font-semibold">{listings.data!.count}</span> listing{listings.data!.count > 1 ? "s" : ""} ·
              from <span className="font-semibold tabular-nums">{sgd(cheapest.price)}</span>
            </p>
            <p className="text-[11px] text-muted-foreground">{cheapest.flat_type} · {cheapest.floor_area_sqft} sqft · {cheapest.storey_range}</p>
          </div>
        )}

        {/* Area PSF trend (resale) */}
        {estate.data?.psf_over_time && estate.data.psf_over_time.length > 1 && (
          <div>
            <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
              <TrendingUp className="h-3.5 w-3.5" /> Area PSF trend
            </div>
            <div className="h-32"><PsfTrendChart series={estate.data.psf_over_time} /></div>
          </div>
        )}

        <p className="text-[10px] text-muted-foreground">
          {b ? "Figures are estate/area medians from HDB resale data." :
            item.price != null ? "Source: URA caveats." : "Estimated resale availability — see Info."}
        </p>
      </div>
    </div>
  );
}
