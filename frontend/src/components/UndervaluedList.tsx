import type { UndervaluedEstate } from "../types";
import { formatPsf } from "../lib/format";

interface Props {
  estates: UndervaluedEstate[];
}

export default function UndervaluedList({ estates }: Props) {
  if (!estates.length) {
    return (
      <div className="p-4 text-sm text-gray-400">
        No undervalued estates detected.
      </div>
    );
  }
  return (
    <ul className="divide-y divide-gray-100">
      {estates.map((e) => (
        <li key={e.planning_area_id} className="py-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-800">{e.name}</span>
            <span className="rounded bg-green-600 px-1.5 py-0.5 text-xs font-semibold text-white">
              -{e.discount_vs_peers_pct}%
            </span>
          </div>
          <div className="text-xs text-gray-500">
            {formatPsf(e.median_psf)} vs peers {formatPsf(e.predicted_psf)}
          </div>
          <div className="text-[11px] text-gray-400">{e.reason}</div>
        </li>
      ))}
    </ul>
  );
}
