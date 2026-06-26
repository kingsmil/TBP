import { Layers } from "lucide-react";
import { MODE_META } from "./types";
import type { Mode } from "./types";

const MODES: Mode[] = ["bto", "resale", "private"];
const SHORT: Record<Mode, string> = { bto: "BTO", resale: "Resale", private: "Private" };

/** Mode selector. Single-tap = focused view of one type. Toggle "Combine" to
 *  overlay several types on the map at once (colour-coded). */
export default function ModeSwitch({ active, onToggle, combine, onCombine, size = "md" }: {
  active: Mode[]; onToggle: (m: Mode) => void;
  combine: boolean; onCombine: (on: boolean) => void; size?: "sm" | "md";
}) {
  const pad = size === "sm" ? "px-2.5 py-1.5 text-xs" : "px-3.5 py-2 text-sm";
  return (
    <div className="inline-flex items-center gap-1">
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
      <button
        type="button" onClick={() => onCombine(!combine)}
        title="Combine multiple property types on the map"
        className={`flex items-center gap-1.5 rounded-full border p-1 font-semibold transition-colors ${pad} ${
          combine ? "border-primary bg-primary text-primary-foreground" : "border-border bg-muted/50 text-muted-foreground hover:text-foreground"
        }`}
      >
        <Layers className="h-3.5 w-3.5" /> Combine
      </button>
    </div>
  );
}
