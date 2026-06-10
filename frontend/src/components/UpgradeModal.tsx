import { useState } from "react";
import { X, Sparkles, Loader2, CheckCircle2 } from "lucide-react";
import { apiCreateCheckout } from "../lib/api";

interface Props {
  onClose: () => void;
  onLoginRequired: () => void;
  isLoggedIn: boolean;
}

const FEATURES = [
  "AI-powered property matching",
  "Natural language search (\"4-room near MRT, under 600k\")",
  "HomeOS agent with clarifying questions",
  "Ranked shortlist with worth-viewing scores",
  "Post-analysis chat with your results",
];

export default function UpgradeModal({ onClose, onLoginRequired, isLoggedIn }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleUpgrade() {
    if (!isLoggedIn) {
      onClose();
      onLoginRequired();
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const { url } = await apiCreateCheckout();
      window.location.href = url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start checkout");
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="relative w-full max-w-sm rounded-2xl border border-border bg-card p-6 shadow-2xl">
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 text-muted-foreground hover:text-foreground"
        >
          <X className="h-4 w-4" />
        </button>

        <div className="mb-4 flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10">
            <Sparkles className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h2 className="font-bold leading-tight">HDB Match Pro</h2>
            <p className="text-xs text-muted-foreground">Unlock AI mode</p>
          </div>
        </div>

        <div className="mb-5 space-y-2">
          {FEATURES.map((f) => (
            <div key={f} className="flex items-start gap-2">
              <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" />
              <span className="text-xs text-foreground">{f}</span>
            </div>
          ))}
        </div>

        <div className="mb-4 rounded-xl bg-primary/5 px-4 py-3 text-center">
          <span className="text-2xl font-bold text-primary">$9.99</span>
          <span className="text-sm text-muted-foreground"> / month</span>
          <p className="mt-0.5 text-[10px] text-muted-foreground">Cancel anytime • Secure via Stripe</p>
        </div>

        {error && (
          <p className="mb-3 rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">{error}</p>
        )}

        <button
          type="button"
          onClick={handleUpgrade}
          disabled={loading}
          className="flex w-full items-center justify-center gap-2 rounded-md bg-primary py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50"
        >
          {loading && <Loader2 className="h-4 w-4 animate-spin" />}
          {isLoggedIn ? "Upgrade to Pro →" : "Sign in to upgrade →"}
        </button>

        {!isLoggedIn && (
          <p className="mt-3 text-center text-xs text-muted-foreground">
            Don't have an account?{" "}
            <button
              type="button"
              className="font-medium text-primary underline-offset-2 hover:underline"
              onClick={() => { onClose(); onLoginRequired(); }}
            >
              Register free
            </button>
          </p>
        )}
      </div>
    </div>
  );
}
