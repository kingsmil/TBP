import type { EstateComparisonRow } from "../types";
import { formatPsf } from "../lib/format";
import { formatScore, scoreColor } from "../lib/score";

interface Props {
  rows: EstateComparisonRow[];
}

function ScorePill({ value }: { value: number | null }) {
  return (
    <span
      className="inline-block rounded px-1.5 py-0.5 text-xs font-medium text-white"
      style={{ backgroundColor: scoreColor(value) }}
    >
      {formatScore(value)}
    </span>
  );
}

export default function EstateComparison({ rows }: Props) {
  if (!rows.length) {
    return <div className="p-4 text-sm text-gray-400">No estates to compare.</div>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs">
        <thead className="text-gray-500">
          <tr>
            <th className="py-1 pr-2">Estate</th>
            <th className="py-1 pr-2">PSF</th>
            <th className="py-1 pr-2">Growth</th>
            <th className="py-1 pr-2">Access</th>
            <th className="py-1 pr-2">Lease</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.planning_area_id} className="border-t border-gray-100">
              <td className="py-1.5 pr-2 font-medium text-gray-800">{r.name}</td>
              <td className="py-1.5 pr-2">{formatPsf(r.median_psf)}</td>
              <td className="py-1.5 pr-2">
                {r.growth_pct != null ? `${r.growth_pct}%` : "—"}
              </td>
              <td className="py-1.5 pr-2">
                <ScorePill value={r.accessibility.combined_score} />
              </td>
              <td className="py-1.5 pr-2">
                {r.lease_profile.avg_remaining_lease != null
                  ? `${r.lease_profile.avg_remaining_lease}y`
                  : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
