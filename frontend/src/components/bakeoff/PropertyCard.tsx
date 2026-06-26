import { Heart, MapPin, GitCompareArrows } from "lucide-react";
import type { CardItem } from "./types";
import type { UiVariant } from "../../lib/uiVariant";
import ScoreBar from "./ScoreBar";

interface Props {
  item: CardItem;
  variant: UiVariant;
  selected?: boolean;
  saved?: boolean;
  comparing?: boolean;
  onSelect?: () => void;
  onSave?: () => void;
  onCompare?: () => void;
  onHover?: (hovering: boolean) => void;
}

const sgd = (n?: number | null) => (n != null ? `$${Math.round(n).toLocaleString()}` : "—");

function IconBtn({ active, onClick, children, label }: {
  active?: boolean; onClick?: () => void; children: React.ReactNode; label: string;
}) {
  return (
    <button
      type="button" aria-label={label} title={label}
      onClick={(e) => { e.stopPropagation(); onClick?.(); }}
      className={`flex h-8 w-8 items-center justify-center rounded-full border transition-colors ${
        active ? "border-primary bg-primary/10 text-primary" : "border-border bg-card text-muted-foreground hover:bg-muted"
      }`}
    >
      {children}
    </button>
  );
}

function Chips({ item }: { item: CardItem }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {item.metrics.map((m) => (
        <span key={m.label} className="rounded-full bg-muted px-2.5 py-1 text-xs text-muted-foreground">
          <span className="font-medium text-foreground">{m.value}</span>
        </span>
      ))}
    </div>
  );
}

export default function PropertyCard(p: Props) {
  const { item, variant, selected, saved, comparing, onSelect, onSave, onCompare, onHover } = p;
  const hoverProps = {
    onMouseEnter: () => onHover?.(true),
    onMouseLeave: () => onHover?.(false),
  };
  const actions = (
    <div className="flex items-center gap-1.5">
      {onSave && <IconBtn active={saved} onClick={onSave} label="Save"><Heart className={`h-4 w-4 ${saved ? "fill-current" : ""}`} /></IconBtn>}
      {onCompare && <IconBtn active={comparing} onClick={onCompare} label="Compare"><GitCompareArrows className="h-4 w-4" /></IconBtn>}
    </div>
  );

  // ── B: premium vertical card ────────────────────────────────────────────────
  if (variant === "b") {
    return (
      <div {...hoverProps} onClick={onSelect}
        className={`group cursor-pointer rounded-2xl border bg-card p-4 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md ${
          selected ? "border-primary ring-1 ring-primary" : "border-border"
        }`}>
        <div className="mb-3 flex items-start justify-between gap-2">
          <div className="min-w-0">
            {item.badge && <span className="mb-1 inline-block rounded-full bg-gradient-to-r from-primary/15 to-primary/5 px-2 py-0.5 text-[11px] font-semibold text-primary">{item.badge}</span>}
            <h3 className="truncate text-sm font-semibold leading-tight">{item.title}</h3>
            <p className="flex items-center gap-1 text-xs text-muted-foreground"><MapPin className="h-3 w-3" />{item.subtitle}</p>
          </div>
          {actions}
        </div>
        <div className="mb-3 flex items-end justify-between">
          <div>
            <div className="text-xl font-bold tabular-nums">{sgd(item.price)}</div>
            <div className="text-[11px] text-muted-foreground">{item.priceLabel}{item.psf != null ? ` · $${item.psf}/sqft` : ""}</div>
          </div>
        </div>
        <Chips item={item} />
        {item.score != null && (
          <div className="mt-3">
            <div className="mb-1 text-[11px] font-medium text-muted-foreground">Match</div>
            <ScoreBar score={item.score} gradient />
          </div>
        )}
      </div>
    );
  }

  // ── C: compact card for split map view ──────────────────────────────────────
  if (variant === "c") {
    return (
      <div {...hoverProps} onClick={onSelect}
        className={`flex cursor-pointer gap-3 rounded-xl border bg-card p-3 transition-colors ${
          selected ? "border-primary ring-1 ring-primary" : "border-border hover:border-primary/50"
        }`}>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <h3 className="truncate text-sm font-semibold">{item.title}</h3>
            <div className="text-sm font-bold tabular-nums">{sgd(item.price)}</div>
          </div>
          <p className="truncate text-xs text-muted-foreground">{item.subtitle}{item.badge ? ` · ${item.badge}` : ""}</p>
          <div className="mt-1.5 flex items-center justify-between gap-2">
            <span className="truncate text-[11px] text-muted-foreground">{item.metrics[0]?.value}</span>
            {item.score != null && <div className="w-24"><ScoreBar score={item.score} /></div>}
          </div>
        </div>
        <div className="flex flex-col justify-between">{actions}</div>
      </div>
    );
  }

  // ── A: calm list row (default) ──────────────────────────────────────────────
  return (
    <div {...hoverProps} onClick={onSelect}
      className={`group flex cursor-pointer flex-col gap-3 rounded-xl border bg-card p-4 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-sm sm:flex-row sm:items-center ${
        selected ? "border-primary ring-1 ring-primary" : "border-border"
      }`}>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          {item.badge && <span className="rounded-md bg-muted px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground">{item.badge}</span>}
          <h3 className="truncate text-sm font-semibold">{item.title}</h3>
        </div>
        <p className="mb-2 flex items-center gap-1 text-xs text-muted-foreground"><MapPin className="h-3 w-3" />{item.subtitle}</p>
        <Chips item={item} />
      </div>
      <div className="flex items-center justify-between gap-3 sm:w-44 sm:flex-col sm:items-end">
        <div className="text-right">
          <div className="text-lg font-bold tabular-nums">{sgd(item.price)}</div>
          <div className="text-[11px] text-muted-foreground">{item.priceLabel}{item.psf != null ? ` · $${item.psf}/sqft` : ""}</div>
        </div>
        {item.score != null && <div className="w-28"><ScoreBar score={item.score} /></div>}
        {actions}
      </div>
    </div>
  );
}
