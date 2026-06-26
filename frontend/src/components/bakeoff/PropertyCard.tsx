import { Heart, GitCompareArrows } from "lucide-react";
import type { CardItem } from "./types";
import { MODE_META } from "./types";
import ScoreBar from "./ScoreBar";

interface Props {
  item: CardItem;
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

/** Compact result card used in the Floating-Glass rail / sheet. */
export default function PropertyCard(p: Props) {
  const { item, selected, saved, comparing, onSelect, onSave, onCompare, onHover } = p;
  return (
    <div
      onMouseEnter={() => onHover?.(true)}
      onMouseLeave={() => onHover?.(false)}
      onClick={onSelect}
      className={`flex cursor-pointer gap-3 rounded-xl border bg-card/80 p-3 transition-colors ${
        selected ? "border-primary ring-1 ring-primary" : "border-border hover:border-primary/50"
      }`}
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <h3 className="flex min-w-0 items-center gap-1.5 truncate text-sm font-semibold">
            <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: MODE_META[item.mode].color }} />
            <span className="truncate">{item.title}</span>
          </h3>
          <div className="shrink-0 text-sm font-bold tabular-nums">{sgd(item.price)}</div>
        </div>
        <p className="truncate text-xs text-muted-foreground">
          {item.subtitle}{item.badge ? ` · ${item.badge}` : ""}
        </p>
        <div className="mt-1.5 flex items-center justify-between gap-2">
          <span className="truncate text-[11px] text-muted-foreground">{item.metrics[0]?.value}</span>
          {item.score != null && <div className="w-24"><ScoreBar score={item.score} /></div>}
        </div>
      </div>
      <div className="flex flex-col justify-between">
        {onSave && <IconBtn active={saved} onClick={onSave} label="Save"><Heart className={`h-4 w-4 ${saved ? "fill-current" : ""}`} /></IconBtn>}
        {onCompare && <IconBtn active={comparing} onClick={onCompare} label="Compare"><GitCompareArrows className="h-4 w-4" /></IconBtn>}
      </div>
    </div>
  );
}
