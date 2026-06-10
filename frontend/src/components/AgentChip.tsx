import type { AgentSource } from "../types";

const LABELS: Record<AgentSource, string> = {
  market: "Market",
  location: "Location",
  lifestyle: "Lifestyle",
  risk: "Risk",
};

const COLORS: Record<AgentSource, string> = {
  market: "bg-emerald-100 text-emerald-700",
  location: "bg-sky-100 text-sky-700",
  lifestyle: "bg-sky-100 text-sky-700",
  risk: "bg-amber-100 text-amber-700",
};

export default function AgentChip({ source }: { source: AgentSource }) {
  return (
    <span
      className={`ml-1 inline-block rounded px-1.5 py-0.5 text-[10px] font-medium ${COLORS[source]}`}
    >
      {LABELS[source]}
    </span>
  );
}
