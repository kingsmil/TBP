import { MODE_META } from "./types";
import type { Mode } from "./types";

const MODES: Mode[] = ["bto", "resale", "private"];
const SHORT: Record<Mode, string> = { bto: "BTO", resale: "Resale", private: "Private" };

/** Multi-select mode toggles. Pick one for a focused view, or combine several to
 *  overlay them on the map (colour-coded). At least one stays active. */
export default function ModeSwitch({ active, onToggle, size = "md" }: {
  active: Mode[]; onToggle: (m: Mode) => void; size?: "sm" | "md";
}) {
  const pad = size === "sm" ? "px-2.5 py-1.5 text-xs" : "px-3.5 py-2 text-sm";
  return (
    <div className="inline-flex gap-1 rounded-full border border-border bg-muted/50 p-1">
      {MODES.map((m) => {
        const on = active.includes(m);
        return (
          <button
            key={m} type="button" onClick={() => onToggle(m)}
            title={MODE_META[m].label}
            className={`flex items-center gap-1.5 rounded-full font-semibold transition-colors ${pad} ${
              on ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <span className="h-2.5 w-2.5 rounded-full" style={{
              background: on ? MODE_META[m].color : "transparent",
              boxShadow: on ? "none" : `inset 0 0 0 1.5px ${MODE_META[m].color}`,
            }} />
            {SHORT[m]}
          </button>
        );
      })}
    </div>
  );
}
