import { useState } from "react";
import { X, Loader2 } from "lucide-react";
import { apiLogin, apiRegister } from "../lib/api";
import { saveAuth, type AuthUser } from "../lib/auth";

interface Props {
  onSuccess: (user: AuthUser) => void;
  onClose?: () => void;
}

export default function AuthModal({ onSuccess, onClose }: Props) {
  const [tab, setTab] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = tab === "login"
        ? await apiLogin(email, password)
        : await apiRegister(email, password);
      const user: AuthUser = { email: res.email, is_subscribed: res.is_subscribed };
      saveAuth(res.token, user);
      onSuccess(user);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="relative w-full max-w-sm rounded-2xl border border-border bg-card p-6 shadow-2xl">
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="absolute right-4 top-4 text-muted-foreground hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        )}

        <h2 className="mb-1 text-lg font-bold">HDB Match</h2>
        <p className="mb-5 text-xs text-muted-foreground">
          {tab === "login" ? "Sign in to your account" : "Create a free account"}
        </p>

        {/* Tabs */}
        <div className="mb-5 flex rounded-lg border border-border p-0.5 text-sm">
          {(["login", "register"] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => { setTab(t); setError(null); }}
              className={`flex-1 rounded-md py-1.5 font-medium transition-colors ${
                tab === t ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {t === "login" ? "Sign in" : "Register"}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-foreground">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
              placeholder="you@example.com"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-foreground">Password</label>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
              placeholder="••••••••"
            />
            {tab === "register" && (
              <p className="mt-1 text-[10px] text-muted-foreground">Minimum 8 characters</p>
            )}
          </div>

          {error && (
            <p className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="flex w-full items-center justify-center gap-2 rounded-md bg-primary py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50"
          >
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            {tab === "login" ? "Sign in" : "Create account"}
          </button>
        </form>

        <div className="mt-4 text-center text-[10px] text-muted-foreground">
          <p>Free account gives access to Explore mode.</p>
          <p className="mt-1 font-medium text-primary">
            AI mode requires a Pro subscription ($9.99/mo).
          </p>
        </div>

        <div className="mt-5 flex items-center justify-center gap-2 border-t border-border pt-4 text-muted-foreground">
          <span className="text-[10px] font-medium uppercase tracking-[0.16em]">Powered by</span>
          <span className="inline-flex items-center gap-1.5 rounded-md bg-[#635bff]/10 px-2 py-1 text-[#635bff]">
            <svg
              aria-hidden="true"
              viewBox="0 0 24 24"
              className="h-4 w-4"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <rect width="24" height="24" rx="6" fill="currentColor" />
              <path
                d="M12.4 8.15c-1.22 0-1.95.38-1.95 1.02 0 .71.92 1.02 2.08 1.42 1.89.65 4.37 1.51 4.37 4.22 0 2.62-2.08 4.19-5.43 4.19-1.39 0-2.95-.27-4.47-.91v-3.08c1.38.75 3.12 1.3 4.47 1.3 1.09 0 1.78-.36 1.78-1.05 0-.77-.99-1.1-2.2-1.53-1.86-.66-4.08-1.55-4.08-4.09 0-2.6 2.01-4.14 5.43-4.14 1.38 0 2.76.21 4.14.75v3.03c-1.26-.61-2.85-1.13-4.14-1.13Z"
                fill="white"
              />
            </svg>
            <span className="text-xs font-bold tracking-tight">stripe</span>
          </span>
        </div>
      </div>
    </div>
  );
}
