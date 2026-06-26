import { useState } from "react";
import { Palette, X, Check } from "lucide-react";
import { type UiVariant, VARIANT_META, setUiVariant } from "../../lib/uiVariant";

/** Floating control to flip between the three bake-off shells (eval only). */
export default function VariantPicker({ current }: { current: UiVariant }) {
  const [open, setOpen] = useState(false);
  const variants: UiVariant[] = ["a", "b", "c"];

  return (
    <div className="fixed bottom-4 right-4 z-[3000] sm:bottom-6 sm:right-6">
      {open && (
        <div className="mb-2 w-64 overflow-hidden rounded-2xl border border-border bg-card shadow-xl">
          <div className="flex items-center justify-between border-b border-border px-3 py-2">
            <span className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Design preview</span>
            <button type="button" onClick={() => setOpen(false)} className="rounded p-0.5 hover:bg-muted"><X className="h-3.5 w-3.5" /></button>
          </div>
          <div className="p-2">
            {variants.map((v) => (
              <button key={v} type="button" onClick={() => setUiVariant(v)}
                className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left transition-colors ${
                  v === current ? "bg-primary/10" : "hover:bg-muted"
                }`}>
                <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                  v === current ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                }`}>{v.toUpperCase()}</span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold">{VARIANT_META[v].name}</span>
                  <span className="block truncate text-[11px] text-muted-foreground">{VARIANT_META[v].tagline}</span>
                </span>
                {v === current && <Check className="h-4 w-4 shrink-0 text-primary" />}
              </button>
            ))}
            <button type="button" onClick={() => setUiVariant(null)}
              className="mt-1 w-full rounded-lg px-2.5 py-2 text-left text-xs font-medium text-muted-foreground hover:bg-muted">
              ← Exit preview (current app)
            </button>
          </div>
        </div>
      )}
      <button type="button" onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-full bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground shadow-lg hover:bg-primary/90">
        <Palette className="h-4 w-4" />
        Design {current.toUpperCase()}
      </button>
    </div>
  );
}
