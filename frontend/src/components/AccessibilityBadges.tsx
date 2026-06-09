import type { AccessibilityScores } from "../types";
import { formatScore, scoreColor } from "../lib/score";

interface Props {
  scores: AccessibilityScores;
}

const ITEMS: { key: keyof AccessibilityScores; label: string }[] = [
  { key: "combined_score", label: "Overall" },
  { key: "mrt_score", label: "MRT" },
  { key: "bus_score", label: "Bus" },
  { key: "school_score", label: "Schools" },
];

export default function AccessibilityBadges({ scores }: Props) {
  return (
    <div className="flex flex-wrap gap-2">
      {ITEMS.map(({ key, label }) => {
        const value = scores[key];
        return (
          <div
            key={key}
            className="flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium text-white"
            style={{ backgroundColor: scoreColor(value) }}
            title={`${label} accessibility`}
          >
            <span>{label}</span>
            <span>{formatScore(value)}</span>
          </div>
        );
      })}
    </div>
  );
}
