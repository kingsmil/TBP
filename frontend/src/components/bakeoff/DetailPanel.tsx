import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { X, Heart, GitCompareArrows, MapPin, TrendingUp, Train, Trees, CalendarClock, KeyRound, Hourglass, ExternalLink, Building2 } from "lucide-react";
import type { CardItem } from "./types";
import { propertyImageUrl, getAppreciation, getEstateAnalytics, getPrivateTransactions } from "../../lib/api";
import PsfTrendChart from "../PsfTrendChart";
import ActiveListingsSection from "../ActiveListingsSection";
import ScoreBar from "./ScoreBar";

const sgd = (n?: number | null) => (n != null ? `$${Math.round(n).toLocaleString()}` : "—");
const MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const fmtMonth = (d?: string | null) => {
  if (!d) return "—";
  const [y, m] = d.split("-");
  const mo = Number(m);
  return m && mo >= 1 && mo <= 12 ? `${MONTHS[mo]} ${y}` : y;
};

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

function InfoRow({ icon: Icon, label, value }: { icon: typeof Train; label: string; value: string }) {
  return (
    <div className="flex items-center gap-2">
      <Icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
      <span className="w-24 shrink-0 text-muted-foreground">{label}</span>
      <span className="flex-1 truncate font-medium">{value}</span>
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
  // Esc deselects the property (closes the panel).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
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
  // Private-only: recent sales in the same project.
  const projectSales = useQuery({
    queryKey: ["bo-proj-sales", item.title],
    queryFn: () => getPrivateTransactions({ project: item.title, limit: 30 }),
    enabled: item.mode === "private" && !!item.title, staleTime: 6e5,
  });

  // Show the SAME sub-scores that drive the match (incl. place-aware commute),
  // not a local re-derivation — otherwise the bars contradict the match number.
  const subs = item.subs;

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
            {subs && (
              <div className="space-y-1.5 pt-1">
                {subs.commute != null && <SubScore icon={Train} label="Commute" score={subs.commute} />}
                {subs.lifestyle != null && <SubScore icon={Trees} label="Lifestyle" score={subs.lifestyle} />}
                {subs.appreciation != null && <SubScore icon={TrendingUp} label="Appreciation" score={subs.appreciation} />}
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

        {/* Active listings (resale) — full list w/ photos, agent + outreach */}
        {b && (
          <div className="overflow-hidden rounded-xl border border-border bg-card/60 [&>div]:border-b-0 [&>div]:p-3">
            <ActiveListingsSection blockId={b.block_id} />
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

        {/* BTO project facts + resale-eligibility (bto) */}
        {item.mode === "bto" && item.bto && (
          <div className="space-y-2.5 rounded-xl border border-border bg-card/60 p-3">
            <div className="flex items-center gap-1.5 text-xs font-semibold"><Building2 className="h-3.5 w-3.5" /> BTO project</div>
            <div className="space-y-1.5 text-xs">
              {item.bto.launch_exercise && <InfoRow icon={CalendarClock} label="Launched" value={item.bto.launch_exercise} />}
              {item.bto.flat_types && <InfoRow icon={Building2} label="Flat types" value={item.bto.flat_types} />}
              {item.bto.estimated_completion_date && <InfoRow icon={CalendarClock} label="Est. completion" value={fmtMonth(item.bto.estimated_completion_date)} />}
              {item.bto.estimated_key_collection_date && <InfoRow icon={KeyRound} label="Est. keys" value={fmtMonth(item.bto.estimated_key_collection_date)} />}
              <InfoRow icon={Hourglass} label="MOP" value={`${item.bto.mop_years} years`} />
            </div>
            <div className="rounded-lg bg-primary/10 p-2.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold">Earliest resale</span>
                <span className="text-sm font-bold text-primary">{fmtMonth(item.bto.estimated_resale_eligible_date)}</span>
              </div>
              <p className="mt-0.5 text-[11px] text-muted-foreground">
                When the {item.bto.mop_years}-year MOP ends and the flat can first be sold on the resale market{item.bto.confidence ? ` · ${item.bto.confidence.toLowerCase()} confidence` : ""}.
              </p>
              {item.bto.confidence_reason && <p className="mt-1 text-[11px] text-muted-foreground">{item.bto.confidence_reason}</p>}
            </div>
            {item.bto.source_url && (
              <a href={item.bto.source_url} target="_blank" rel="noreferrer"
                className="inline-flex items-center gap-1 text-[11px] font-medium text-primary hover:underline">
                <ExternalLink className="h-3 w-3" /> HDB source
              </a>
            )}
          </div>
        )}

        {/* Recent sales in this project (private) */}
        {item.mode === "private" && (projectSales.data?.results?.length ?? 0) > 0 && (
          <div className="rounded-xl border border-border bg-card/60 p-3">
            <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold"><TrendingUp className="h-3.5 w-3.5" /> Recent sales in this project</div>
            <div className="space-y-1.5">
              {projectSales.data!.results.slice(0, 6).map((t) => (
                <div key={t.id} className="flex items-center justify-between gap-2 text-xs">
                  <span className="text-muted-foreground">{t.sale_date.slice(0, 7)}{t.area_sqft ? ` · ${t.area_sqft} sqft` : ""}</span>
                  <span className="shrink-0 tabular-nums font-medium">{sgd(t.price)}{t.psf != null ? ` · $${t.psf}/sqft` : ""}</span>
                </div>
              ))}
            </div>
            {projectSales.data!.results.length > 6 && (
              <p className="mt-1.5 text-[11px] text-muted-foreground">+{projectSales.data!.results.length - 6} more recent sales</p>
            )}
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
