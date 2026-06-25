import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { MapPin, X, Trash2, Plus, LogIn, Home, Briefcase, GraduationCap, Heart, Users, Star } from "lucide-react";
import type { AuthUser } from "../lib/auth";
import type { SavedLocationType } from "../types";
import { authState, canPersist, loadLocations, addLocation, removeLocation, loadPreferences } from "../lib/userState";

const TYPE_META: Record<SavedLocationType, { label: string; icon: typeof Home }> = {
  home: { label: "Home", icon: Home },
  work: { label: "Work", icon: Briefcase },
  school: { label: "School", icon: GraduationCap },
  partner: { label: "Partner", icon: Heart },
  family: { label: "Family", icon: Users },
  custom: { label: "Custom", icon: Star },
};
const TYPES = Object.keys(TYPE_META) as SavedLocationType[];

interface Props {
  authUser: AuthUser | null;
  onClose: () => void;
  onSignIn: () => void;
}

export default function SavedPlacesPanel({ authUser, onClose, onSignIn }: Props) {
  const state = authState();
  const persist = canPersist();
  const qc = useQueryClient();

  const locs = useQuery({ queryKey: ["saved-locations", state], queryFn: loadLocations });
  const prefs = useQuery({ queryKey: ["saved-prefs", state], queryFn: loadPreferences });

  const [label, setLabel] = useState("");
  const [type, setType] = useState<SavedLocationType>("home");
  const [address, setAddress] = useState("");
  const [postal, setPostal] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const refresh = () => qc.invalidateQueries({ queryKey: ["saved-locations"] });

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!label.trim()) return;
    setBusy(true);
    try {
      await addLocation({
        label: label.trim(), location_type: type,
        address: address.trim() || null, postal_code: postal.trim() || null,
        lat: null, lng: null,
      });
      setLabel(""); setAddress(""); setPostal(""); setType("home");
      refresh();
    } finally {
      setBusy(false);
    }
  }

  async function handleRemove(id: number) {
    await removeLocation(id);
    refresh();
  }

  const items = locs.data ?? [];

  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="flex max-h-[85vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-xl"
        onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-5 py-3">
          <div className="flex items-center gap-2">
            <MapPin className="h-4 w-4 text-primary" />
            <h2 className="text-base font-bold">Saved places &amp; preferences</h2>
          </div>
          <button type="button" onClick={onClose} className="rounded-md p-1 hover:bg-muted"><X className="h-4 w-4" /></button>
        </div>

        {/* Auth-state banner */}
        <div className="px-5 pt-4">
          {state === "anonymous" && (
            <div className="flex items-start gap-2 rounded-lg border border-amber-300/60 bg-amber-50 p-3 text-xs text-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
              <LogIn className="mt-0.5 h-4 w-4 shrink-0" />
              <div className="space-y-1.5">
                <p>You&apos;re browsing as a guest. Places you add are kept <strong>on this device only</strong>.</p>
                <button type="button" onClick={onSignIn}
                  className="rounded-md bg-primary px-2.5 py-1 font-semibold text-primary-foreground hover:bg-primary/90">
                  Sign in to save permanently
                </button>
              </div>
            </div>
          )}
          {state === "dev" && (
            <div className="rounded-lg border border-sky-300/60 bg-sky-50 p-2.5 text-xs text-sky-900 dark:bg-sky-950/30 dark:text-sky-200">
              Dev mode — saving to the local dev account (auth bypass).
            </div>
          )}
          {state === "logged-in" && (
            <div className="rounded-lg border border-emerald-300/60 bg-emerald-50 p-2.5 text-xs text-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-200">
              Signed in as <strong>{authUser?.email}</strong> — saved to your account.
            </div>
          )}
        </div>

        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto p-5">
          {/* Add location */}
          <form onSubmit={handleAdd} className="space-y-2 rounded-xl border border-border bg-background/50 p-3">
            <div className="text-xs font-semibold text-muted-foreground">Add a place</div>
            <div className="flex flex-wrap gap-2">
              <select value={type} onChange={(e) => setType(e.target.value as SavedLocationType)}
                className="h-8 rounded-md border border-input bg-background px-2 text-xs">
                {TYPES.map((t) => <option key={t} value={t}>{TYPE_META[t].label}</option>)}
              </select>
              <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Label (e.g. Mum's place)"
                className="h-8 min-w-[140px] flex-1 rounded-md border border-input bg-background px-2 text-xs" />
            </div>
            <div className="flex flex-wrap gap-2">
              <input value={address} onChange={(e) => setAddress(e.target.value)} placeholder="Address (optional)"
                className="h-8 min-w-[160px] flex-1 rounded-md border border-input bg-background px-2 text-xs" />
              <input value={postal} onChange={(e) => setPostal(e.target.value)} placeholder="Postal"
                className="h-8 w-24 rounded-md border border-input bg-background px-2 text-xs" />
            </div>
            <button type="submit" disabled={busy || !label.trim()}
              className="flex items-center gap-1.5 rounded-md bg-primary px-2.5 py-1.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
              <Plus className="h-3.5 w-3.5" /> Add place
            </button>
          </form>

          {/* Locations list */}
          <div className="space-y-2">
            <div className="text-xs font-semibold text-muted-foreground">Your places ({items.length})</div>
            {locs.isLoading && <p className="text-xs text-muted-foreground">Loading…</p>}
            {!locs.isLoading && items.length === 0 && (
              <p className="rounded-md border border-dashed border-border bg-muted/40 p-3 text-center text-xs text-muted-foreground">
                No saved places yet. Add home, work, school or your partner&apos;s place to reuse across BTO, resale &amp; private searches.
              </p>
            )}
            {items.map((l) => {
              const Meta = TYPE_META[l.location_type] ?? TYPE_META.custom;
              const Icon = Meta.icon;
              return (
                <div key={l.id} className="flex items-center gap-3 rounded-lg border border-border bg-card px-3 py-2">
                  <Icon className="h-4 w-4 shrink-0 text-primary" />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">{l.label}</div>
                    <div className="truncate text-[11px] text-muted-foreground">
                      {Meta.label}{l.address ? ` · ${l.address}` : ""}{l.postal_code ? ` · ${l.postal_code}` : ""}
                    </div>
                  </div>
                  <button type="button" onClick={() => handleRemove(l.id)} title="Remove"
                    className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-red-600">
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              );
            })}
          </div>

          {/* Preference summary */}
          {prefs.data && Object.keys(prefs.data).length > 0 && (
            <div className="space-y-1.5 rounded-xl border border-border bg-background/50 p-3">
              <div className="text-xs font-semibold text-muted-foreground">Saved preferences</div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px]">
                <Pref k="Last mode" v={prefs.data.last_search_mode} />
                <Pref k="Max budget" v={prefs.data.max_budget ? `$${Number(prefs.data.max_budget).toLocaleString()}` : null} />
                <Pref k="Preferred towns" v={prefs.data.preferred_towns} />
                <Pref k="Flat types" v={prefs.data.preferred_flat_types} />
                <Pref k="Property modes" v={prefs.data.preferred_property_modes} />
              </div>
              <p className="pt-1 text-[10px] text-muted-foreground">
                Preferences are saved automatically from your searches and {persist ? "synced to your account" : "kept on this device"}.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Pref({ k, v }: { k: string; v: string | number | null | undefined }) {
  if (v == null || v === "") return null;
  return (
    <div className="flex justify-between gap-2">
      <span className="text-muted-foreground">{k}</span>
      <span className="truncate font-medium">{String(v)}</span>
    </div>
  );
}
