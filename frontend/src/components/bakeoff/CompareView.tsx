import { X, Trash2 } from "lucide-react";
import type { CardItem } from "./types";
import { MODE_META } from "./types";
import { propertyImageUrl } from "../../lib/api";

const sgd = (n?: number | null) => (n != null ? `$${Math.round(n).toLocaleString()}` : "—");

interface Props {
  items: CardItem[];
  onRemove: (id: string) => void;
  onClear: () => void;
  onClose: () => void;
}

/** Side-by-side comparison of the shortlisted properties. Columns per property,
 *  aligned rows per attribute (price, psf, match + each card's own metrics). */
export default function CompareView({ items, onRemove, onClear, onClose }: Props) {
  // Union of metric labels across the compared items, in first-seen order.
  const labels: string[] = [];
  const seen = new Set<string>();
  for (const it of items) for (const m of it.metrics) if (!seen.has(m.label)) { seen.add(m.label); labels.push(m.label); }
  const metricVal = (it: CardItem, label: string) => it.metrics.find((m) => m.label === label)?.value ?? "—";

  return (
    <div className="fixed inset-0 z-[2500] flex items-end justify-center bg-black/40 p-0 sm:items-center sm:p-6" onClick={onClose}>
      <div className="bo-glass bo-spring-up flex max-h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-t-2xl sm:rounded-2xl"
        onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-5 py-3">
          <h2 className="text-base font-bold">Compare ({items.length})</h2>
          <div className="flex items-center gap-2">
            {items.length > 0 && (
              <button type="button" onClick={onClear}
                className="flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-muted-foreground hover:bg-muted">
                <Trash2 className="h-3.5 w-3.5" /> Clear
              </button>
            )}
            <button type="button" onClick={onClose} className="rounded-md p-1 hover:bg-muted"><X className="h-4 w-4" /></button>
          </div>
        </div>

        {items.length === 0 ? (
          <div className="p-10 text-center text-sm text-muted-foreground">
            Nothing to compare yet — tap the compare button (⇄) on a property.
          </div>
        ) : (
          <div className="min-h-0 flex-1 overflow-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="sticky top-0 bg-card/95 backdrop-blur">
                  <th className="w-24 px-3 py-2" />
                  {items.map((it) => (
                    <th key={it.id} className="min-w-[150px] border-l border-border px-3 py-2 text-left align-top">
                      <div className="relative mb-2 h-20 overflow-hidden rounded-lg bg-muted">
                        {(it.block?.block_id != null || (it.lat != null && it.lon != null)) && (
                          <img src={propertyImageUrl({ blockId: it.block?.block_id, lat: it.lat, lon: it.lon })}
                            alt="" className="h-full w-full object-cover" onError={(e) => { e.currentTarget.style.display = "none"; }} />
                        )}
                        <button type="button" onClick={() => onRemove(it.id)}
                          className="absolute right-1 top-1 flex h-6 w-6 items-center justify-center rounded-full bg-card/85 hover:bg-card">
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: MODE_META[it.mode].color }} />
                        <span className="truncate text-xs font-bold" title={it.title}>{it.title}</span>
                      </div>
                      <div className="truncate text-[11px] font-normal text-muted-foreground">{it.subtitle}</div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <Row label="Price" items={items} render={(it) => <span className="font-semibold tabular-nums">{sgd(it.price)}</span>} />
                <Row label="$/sqft" items={items} render={(it) => <span className="tabular-nums">{it.psf != null ? `$${it.psf}` : "—"}</span>} />
                <Row label="Match" items={items} render={(it) => (it.score != null ? `${it.score}/100` : "—")} />
                {labels.map((label) => (
                  <Row key={label} label={label} items={items} render={(it) => metricVal(it, label)} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function Row({ label, items, render }: {
  label: string; items: CardItem[]; render: (it: CardItem) => React.ReactNode;
}) {
  return (
    <tr className="border-t border-border/60">
      <td className="px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{label}</td>
      {items.map((it) => (
        <td key={it.id} className="border-l border-border px-3 py-2">{render(it)}</td>
      ))}
    </tr>
  );
}
