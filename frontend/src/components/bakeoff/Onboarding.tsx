import { ArrowRight, LogIn, Check } from "lucide-react";
import type { SearchFilters } from "../../types";
import type { Mode, Weights } from "./types";
import { SCORE_FACTORS, MODE_META } from "./types";

interface Props {
  weights: Weights;
  setWeights: (w: Weights) => void;
  modes: Mode[];
  setModes: (m: Mode[]) => void;
  filters: SearchFilters;
  setFilters: (f: SearchFilters) => void;
  authEmail: string | null;
  onSignIn: () => void;
  onFinish: () => void;
}

const MODE_ORDER: Mode[] = ["resale", "bto", "private"];

export default function Onboarding(p: Props) {
  const active = p.modes[0] ?? "resale";
  const set = (key: string, v: number) => p.setWeights({ ...p.weights, [key]: v });

  return (
    <div className="fixed inset-0 z-[1900] flex items-center justify-center overflow-y-auto bg-gradient-to-br from-primary/15 via-background to-background p-4">
      <div className="bo-spring-up bo-glass my-auto w-full max-w-lg rounded-3xl p-6 sm:p-8">
        <div className="mb-5">
          <h1 className="text-xl font-bold sm:text-2xl">Find your ideal home</h1>
          <p className="mt-1 text-sm text-muted-foreground">A couple of quick things — you can change all of this later on the map.</p>
        </div>

        {/* Product */}
        <div className="mb-5">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">I'm looking at</div>
          <div className="grid grid-cols-3 gap-2">
            {MODE_ORDER.map((m) => {
              const on = active === m;
              return (
                <button key={m} type="button" onClick={() => p.setModes([m])}
                  className={`rounded-xl border p-3 text-left transition-colors ${on ? "border-primary bg-primary/10" : "border-border hover:bg-muted"}`}>
                  <span className="flex items-center gap-1.5 text-sm font-semibold">
                    <span className="inline-block h-2 w-2 rounded-full" style={{ background: MODE_META[m].color }} />
                    {MODE_META[m].label}
                    {on && <Check className="ml-auto h-3.5 w-3.5 text-primary" />}
                  </span>
                  <span className="mt-0.5 block text-[11px] text-muted-foreground">{MODE_META[m].blurb}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Budget — resale/private have a price; BTO doesn't */}
        {active !== "bto" && (
          <div className="mb-5">
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">Max budget (optional)</label>
            <div className="flex items-center gap-2 rounded-xl border border-border bg-card px-3">
              <span className="text-sm text-muted-foreground">$</span>
              <input type="number" inputMode="numeric" placeholder="e.g. 650000"
                value={p.filters.max_price ?? ""}
                onChange={(e) => p.setFilters({ ...p.filters, max_price: e.target.value ? Number(e.target.value) : undefined })}
                className="h-11 flex-1 bg-transparent text-sm outline-none" />
            </div>
          </div>
        )}

        {/* Priorities — the match score is resale-only */}
        {active === "resale" ? (
          <div className="mb-6">
            <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">What matters most?</div>
            <p className="mb-3 text-[11px] text-muted-foreground">Drag to set how much each one counts toward a home's match score.</p>
            <div className="space-y-3">
              {SCORE_FACTORS.map((f) => (
                <div key={f.key}>
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <span className="font-medium">{f.label}</span>
                    <span className="tabular-nums text-muted-foreground">{p.weights[f.key] ?? 0}</span>
                  </div>
                  <input type="range" min={0} max={50} value={p.weights[f.key] ?? 0}
                    onChange={(e) => set(f.key, Number(e.target.value))} className="w-full accent-primary" />
                </div>
              ))}
            </div>
          </div>
        ) : (
          <p className="mb-6 rounded-xl border border-border bg-muted/40 p-3 text-[11px] text-muted-foreground">
            Match scoring &amp; filters apply to <span className="font-medium text-foreground">Resale</span> homes. You can switch modes anytime on the map.
          </p>
        )}

        {/* Actions */}
        <div className="flex items-center gap-3">
          <button type="button" onClick={p.onFinish}
            className="flex h-11 flex-1 items-center justify-center gap-2 rounded-full bg-primary px-4 text-sm font-semibold text-primary-foreground hover:bg-primary/90">
            See my homes <ArrowRight className="h-4 w-4" />
          </button>
          <button type="button" onClick={p.onFinish}
            className="h-11 rounded-full px-4 text-sm font-medium text-muted-foreground hover:bg-muted">
            Skip
          </button>
        </div>

        {/* Auth hint */}
        <div className="mt-4 text-center text-xs text-muted-foreground">
          {p.authEmail ? (
            <>Signed in as <span className="font-medium text-foreground">{p.authEmail}</span> — saved across devices.</>
          ) : (
            <button type="button" onClick={p.onSignIn} className="inline-flex items-center gap-1 font-medium text-primary hover:underline">
              <LogIn className="h-3.5 w-3.5" /> Sign in to save across devices
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
