import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { MonthlyPoint } from "../types";

interface Props {
  series: MonthlyPoint[];
}

export default function PsfTrendChart({ series }: Props) {
  if (!series.length) {
    return <div className="p-4 text-sm text-gray-400">No transaction data.</div>;
  }
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={series} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#b3c3d2" />
        <XAxis dataKey="month" tick={{ fontSize: 10, fill: "#889688" }} />
        <YAxis tick={{ fontSize: 10, fill: "#889688" }} width={48} />
        <Tooltip />
        <Line
          type="monotone"
          dataKey="median_psf"
          stroke="#6f86aa"
          strokeWidth={2}
          dot={false}
          name="Median PSF"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
