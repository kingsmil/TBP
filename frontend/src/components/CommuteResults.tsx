import type { CommuteResultRow } from "../types";
import { bandColor, formatMinutes } from "../lib/commute";

interface Props {
  rows: CommuteResultRow[];
}

export default function CommuteResults({ rows }: Props) {
  if (!rows.length) {
    return (
      <div className="p-4 text-sm text-gray-400">
        Add destinations to rank blocks by commute fit.
      </div>
    );
  }
  return (
    <ul className="divide-y divide-gray-100">
      {rows.map((r) => (
        <li key={r.block_id} className="flex items-center justify-between py-2">
          <div>
            <div className="text-sm font-medium text-gray-800">
              Blk {r.block_number}
            </div>
            <div className="text-xs text-gray-500">{r.town}</div>
          </div>
          <div className="flex items-center gap-3 text-right">
            <span className="text-xs text-gray-500">
              {formatMinutes(r.weekly_minutes)}/wk
            </span>
            <span
              className="inline-block w-8 rounded text-center text-xs font-semibold text-white"
              style={{ backgroundColor: bandColor(r.band) }}
            >
              {Math.round(r.commute_score)}
            </span>
          </div>
        </li>
      ))}
    </ul>
  );
}
