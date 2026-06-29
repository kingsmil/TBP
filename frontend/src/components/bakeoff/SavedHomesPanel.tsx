import { useEffect } from "react";
import { Heart, X, Trash2, Home } from "lucide-react";
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

        <div className="min-h-0 flex-1 space-y-2.5 overflow-y-auto p-4">
          {snaps.length === 0 && (
            <div className="flex flex-col items-center gap-2 rounded-2xl border border-dashed border-border bg-muted/30 px-6 py-10 text-center">
              <Heart className="h-7 w-7 text-muted-foreground/50" />
              <p className="text-sm font-medium">No saved homes yet</p>
              <p className="text-xs text-muted-foreground">Tap the ♥ on any property to keep it here.</p>
            </div>
          )}
          {snaps.map((s) => {
            const c = MODE_META[s.mode].color;
            return (
              <div key={s.id}
                className="group relative flex items-stretch gap-3 overflow-hidden rounded-2xl border border-border bg-card/70 p-2.5 transition-colors hover:border-primary/40 hover:bg-card">
                <button type="button" onClick={() => onSelect(s.id)}
                  className="flex min-w-0 flex-1 items-center gap-3 text-left">
                  {/* Thumbnail with a fallback glyph */}
                  <div className="relative h-16 w-16 shrink-0 overflow-hidden rounded-xl bg-muted">
                    <div className="absolute inset-0 flex items-center justify-center text-muted-foreground/40">
                      <Home className="h-6 w-6" />
                    </div>
                    <img
                      src={propertyImageUrl({ blockId: s.blockId, lat: s.lat, lon: s.lon })}
                      alt="" loading="lazy"
                      onError={(e) => { (e.currentTarget as HTMLImageElement).style.opacity = "0"; }}
                      className="relative h-full w-full object-cover" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <span className="inline-block rounded-full px-1.5 py-0.5 text-[10px] font-semibold"
                      style={{ color: c, backgroundColor: `${c}1a` }}>{MODE_META[s.mode].label}</span>
                    <div className="mt-1 truncate text-sm font-semibold">{s.title}</div>
                    <div className="truncate text-[11px] text-muted-foreground">{s.subtitle}</div>
                    <div className="mt-1 flex items-baseline gap-1.5">
                      <span className="text-sm font-bold tabular-nums">{sgd(s.price)}</span>
                      {s.psf != null && <span className="text-[11px] text-muted-foreground">${s.psf}/sqft</span>}
                    </div>
                  </div>
                  {s.score != null && (
                    <div className="flex shrink-0 flex-col items-center justify-center rounded-xl bg-primary/10 px-2.5 py-1.5 text-primary">
                      <span className="text-base font-bold leading-none tabular-nums">{s.score}</span>
                      <span className="text-[9px] font-semibold uppercase tracking-wide">match</span>
                    </div>
                  )}
                </button>
                <button type="button" onClick={() => onRemove(s.id)} title="Remove"
                  className="absolute right-1.5 top-1.5 flex h-7 w-7 items-center justify-center rounded-full bg-card/90 text-muted-foreground opacity-0 shadow-sm transition-opacity hover:text-red-600 group-hover:opacity-100">
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
