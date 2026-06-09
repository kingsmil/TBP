import type { AppreciationResult } from "../types";
import { confidenceColor, formatLevel, riskColor } from "../lib/appreciation";

interface Props {
  data: AppreciationResult;
}

function Pill({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="flex items-center gap-1 text-xs">
      <span className="text-gray-500">{label}</span>
      <span
        className="rounded px-1.5 py-0.5 font-medium text-white"
        style={{ backgroundColor: color }}
      >
        {value}
      </span>
    </div>
  );
}

export default function AppreciationCard({ data }: Props) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-3 shadow-sm">
      <div className="flex items-baseline justify-between">
        <span className="text-xs uppercase tracking-wide text-gray-500">
          Appreciation
        </span>
        <span className="text-2xl font-semibold text-gray-900">
          {data.appreciation_score ?? "—"}
        </span>
      </div>
      <div className="mt-2 flex gap-4">
        <Pill label="Risk" value={formatLevel(data.risk_level)}
              color={riskColor(data.risk_level)} />
        <Pill label="Confidence" value={formatLevel(data.confidence_level)}
              color={confidenceColor(data.confidence_level)} />
      </div>
      <p className="mt-2 text-[10px] leading-tight text-gray-400">{data.disclaimer}</p>
    </div>
  );
}
