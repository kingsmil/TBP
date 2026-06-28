import { useEffect } from "react";
import { Heart, X, Trash2, MapPin } from "lucide-react";
import { propertyImageUrl } from "../../lib/api";
import type { Mode } from "./types";
import { MODE_META } from "./types";

/** A lightweight, persisted snapshot of a hearted property — enough to show the
 *  saved-homes list and jump to it on the map, even across reloads / mode
 *  switches when the live card isn't loaded. */
export interface SavedSnapshot {
  id: string;
  mode: Mode;
  title: string;
  subtitle: string;
  price: number | null;
  priceLabel: string;
  psf: number | null;
  score: number | null;
  lat: number | null;
  lon: number | null;
  blockId?: number;
}

const sgd = (n?: number | null) => (n != null ? `$${Math.round(n).toLocaleString()}` : "—");

interface Props {
  snaps: SavedSnapshot[];
  onSelect: (id: string) => void;
  onRemove: (id: string) => void;
  onClose: () => void;
}

export default function SavedHomesPanel({ snaps, onSelect, onRemove, onClose }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="bo-glass flex max-h-[85vh] w-full max-w-md flex-col overflow-hidden rounded-2xl"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-border/60 px-5 py-3">
          <div className="flex items-center gap-2">
            <Heart className="h-4 w-4 fill-current text-primary" />
            <h2 className="text-base font-bold">Saved homes</h2>
            <span className="text-xs text-muted-foreground">({snaps.length})</span>
          </div>
          <button type="button" onClick={onClose} className="rounded-md p-1 hover:bg-muted"><X className="h-4 w-4" /></button>
        </div>

        <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-4">
          {snaps.length === 0 && (
            <p className="rounded-lg border border-dashed border-border bg-muted/40 p-4 text-center text-xs text-muted-foreground">
              No saved homes yet. Tap the ♥ on any property to save it here.
            </p>
          )}
          {snaps.map((s) => (
            <div key={s.id}
              className="group flex items-center gap-3 rounded-xl border border-border bg-card/70 p-2 text-left">
              <button type="button" onClick={() => onSelect(s.id)}
                className="flex min-w-0 flex-1 items-center gap-3">
                <img
                  src={propertyImageUrl({ blockId: s.blockId, lat: s.lat, lon: s.lon })}
                  alt="" loading="lazy"
                  onError={(e) => { (e.currentTarget as HTMLImageElement).style.visibility = "hidden"; }}
                  className="h-12 w-12 shrink-0 rounded-lg object-cover" />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-semibold">{s.title}</div>
                  <div className="flex items-center gap-1 truncate text-[11px] text-muted-foreground">
                    <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: MODE_META[s.mode].color }} />
                    {s.subtitle}
                  </div>
                  <div className="text-xs font-medium tabular-nums">
                    {sgd(s.price)}{s.psf != null ? ` · $${s.psf}/sqft` : ""}
                    {s.score != null ? <span className="ml-1 text-primary">· {s.score} match</span> : null}
                  </div>
                </div>
              </button>
              <div className="flex shrink-0 flex-col items-center gap-1">
                <button type="button" onClick={() => onSelect(s.id)} title="Show on map"
                  className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground">
                  <MapPin className="h-4 w-4" />
                </button>
                <button type="button" onClick={() => onRemove(s.id)} title="Remove"
                  className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-red-600">
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
