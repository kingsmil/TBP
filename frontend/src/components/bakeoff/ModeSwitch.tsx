import { Building2, KeyRound, Landmark } from "lucide-react";
import type { Mode } from "./types";

const MODES: { key: Mode; label: string; icon: typeof Building2 }[] = [
  { key: "bto", label: "BTO", icon: Building2 },
  { key: "resale", label: "Resale", icon: KeyRound },
  { key: "private", label: "Private", icon: Landmark },
];

/** Segmented control shared by every variant. */
export default function ModeSwitch({ mode, onChange, size = "md" }: {
  mode: Mode; onChange: (m: Mode) => void; size?: "sm" | "md";
}) {
  const pad = size === "sm" ? "px-2.5 py-1.5 text-xs" : "px-3.5 py-2 text-sm";
  return (
    <div className="inline-flex rounded-full border border-border bg-muted/50 p-1">
      {MODES.map(({ key, label, icon: Icon }) => (
        <button
          key={key} type="button" onClick={() => onChange(key)}
          className={`flex items-center gap-1.5 rounded-full font-semibold transition-colors ${pad} ${
            mode === key ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <Icon className="h-4 w-4" />
          {label}
        </button>
      ))}
    </div>
  );
}
