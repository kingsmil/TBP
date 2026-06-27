import { useState } from "react";
import { Gauge, X } from "lucide-react";
import { SCORE_FACTORS, type Weights } from "./types";

interface Props {
  weights: Weights;
  setWeights: (w: Weights) => void;
  colorByScore: boolean;
  setColorByScore: (on: boolean) => void;
}

/** Floating glass "Priorities" control — re-weights the resale match score live. */
export default function PrioritiesControl(p: Props) {
  const [open, setOpen] = useState(false);
  const total = SCORE_FACTORS.reduce((s, f) => s + (p.weights[f.key] ?? 0), 0) || 1;
  const set = (k: string, v: number) => p.setWeights({ ...p.weights, [k]: v });
  const balance = () => {
    const even = Math.round(100 / SCORE_FACTORS.length);
    const w: Weights = {};
    SCORE_FACTORS.forEach((f) => { w[f.key] = even; });
    p.setWeights(w);
  };

  return (
    <div className="relative">
      <button type="button" onClick={() => setOpen((o) => !o)}
        className="bo-glass flex h-11 items-center gap-2 rounded-full px-3.5 text-sm font-semibold">
        <Gauge className="h-4 w-4" /> <span className="hidden sm:inline">Priorities</span>
      </button>
      {open && (
        <div className="bo-glass absolute right-0 top-12 z-[1100] w-72 rounded-2xl p-4">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-bold">Your priorities</h3>
            <button type="button" onClick={() => setOpen(false)} className="rounded p-0.5 hover:bg-muted"><X className="h-4 w-4" /></button>
          </div>
          <p className="mb-3 text-[11px] text-muted-foreground">
            How much each factor matters. Resale match scores + the “Recommended” sort update live.
          </p>
          <div className="space-y-2.5">
            {SCORE_FACTORS.map((f) => {
              const w = p.weights[f.key] ?? 0;
              const pct = Math.round((w / total) * 100);
              return (
                <div key={f.key}>
                  <div className="mb-0.5 flex justify-between text-xs">
                    <span className="font-medium">{f.label}</span>
                    <span className="tabular-nums text-muted-foreground">{pct}%</span>
                  </div>
                  <input type="range" min={0} max={100} step={5} value={w}
                    onChange={(e) => set(f.key, Number(e.target.value))} className="w-full accent-primary" />
                </div>
              );
            })}
          </div>
          <div className="mt-3 flex items-center justify-between border-t border-border/60 pt-3">
            <button type="button" onClick={balance} className="text-xs font-medium text-primary hover:underline">Balance evenly</button>
            <label className="flex cursor-pointer items-center gap-2 text-xs font-medium">
              <input type="checkbox" checked={p.colorByScore} onChange={(e) => p.setColorByScore(e.target.checked)} className="h-4 w-4 accent-primary" />
              Colour pins by score
            </label>
          </div>
        </div>
      )}
    </div>
  );
}
