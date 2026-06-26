import { useState } from "react";
import { X, Heart, GitCompareArrows, MapPin } from "lucide-react";
import type { CardItem } from "./types";
import { propertyImageUrl } from "../../lib/api";
import ScoreBar from "./ScoreBar";

const sgd = (n?: number | null) => (n != null ? `$${Math.round(n).toLocaleString()}` : "—");

interface Props {
  item: CardItem;
  saved: boolean;
  comparing: boolean;
  onClose: () => void;
  onSave: () => void;
  onCompare: () => void;
}

/** Floating glass detail card that springs up over the map when a pin/result
 *  is selected. Shared by all three map-first variants. */
export default function DetailCard({ item, saved, comparing, onClose, onSave, onCompare }: Props) {
  const [imgOk, setImgOk] = useState(true);
  const hasCoords = item.lat != null && item.lon != null;
  const canImage = imgOk && (item.block?.block_id != null || hasCoords);
  const imgUrl = propertyImageUrl({ blockId: item.block?.block_id, lat: item.lat, lon: item.lon });
  return (
    <div className="bo-glass bo-spring-up pointer-events-auto w-[min(92vw,380px)] overflow-hidden rounded-2xl">
      {/* Photo: real listing photo → Street View → OneMap map; gradient fallback */}
      <div className="relative h-32 bg-gradient-to-br from-primary/25 via-primary/10 to-transparent">
        {canImage && (
          <img src={imgUrl} alt={item.title} loading="lazy"
            onError={() => setImgOk(false)}
            className="absolute inset-0 h-full w-full object-cover" />
        )}
        <button type="button" onClick={onClose}
          className="absolute right-2 top-2 flex h-7 w-7 items-center justify-center rounded-full bg-card/80 text-foreground shadow-sm hover:bg-card">
          <X className="h-4 w-4" />
        </button>
        {item.badge && (
          <span className="absolute left-3 top-3 rounded-full bg-card/85 px-2 py-0.5 text-[11px] font-semibold">{item.badge}</span>
        )}
      </div>

      <div className="p-4">
        <h3 className="truncate text-base font-bold leading-tight">{item.title}</h3>
        <p className="mb-3 flex items-center gap-1 text-xs text-muted-foreground"><MapPin className="h-3 w-3" />{item.subtitle}</p>

        <div className="mb-3 flex items-end justify-between">
          <div>
            <div className="text-2xl font-bold tabular-nums">{sgd(item.price)}</div>
            <div className="text-[11px] text-muted-foreground">{item.priceLabel}{item.psf != null ? ` · $${item.psf}/sqft` : ""}</div>
          </div>
          <div className="flex gap-1.5">
            <button type="button" onClick={onSave}
              className={`flex h-9 w-9 items-center justify-center rounded-full border transition-colors ${saved ? "border-primary bg-primary/10 text-primary" : "border-border hover:bg-muted"}`}>
              <Heart className={`h-4 w-4 ${saved ? "fill-current" : ""}`} />
            </button>
            <button type="button" onClick={onCompare}
              className={`flex h-9 w-9 items-center justify-center rounded-full border transition-colors ${comparing ? "border-primary bg-primary/10 text-primary" : "border-border hover:bg-muted"}`}>
              <GitCompareArrows className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="mb-3 grid grid-cols-3 gap-2">
          {item.metrics.map((m) => (
            <div key={m.label} className="rounded-xl bg-muted/60 p-2 text-center">
              <div className="truncate text-xs font-semibold">{m.value}</div>
              <div className="truncate text-[10px] text-muted-foreground">{m.label}</div>
            </div>
          ))}
        </div>

        {item.score != null && (
          <div>
            <div className="mb-1 text-[11px] font-medium text-muted-foreground">Match score</div>
            <ScoreBar score={item.score} gradient />
          </div>
        )}
      </div>
    </div>
  );
}
