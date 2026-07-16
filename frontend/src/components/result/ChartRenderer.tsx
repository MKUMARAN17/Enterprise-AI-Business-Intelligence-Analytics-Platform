/**
 * Renders the backend's chosen visualization with recharts.
 *
 * The backend's Visualization Agent already decided the chart `kind` and the
 * `x`/`y` encodings from the data shape + the user's phrasing; this component
 * just draws that decision. It builds row records from `columns`/`rows` and maps
 * kind → the matching recharts chart. (The backend also ships a Vega-Lite `spec`
 * for clients that prefer it; here we render natively with recharts, matching
 * the reference frontend's charting choice.)
 */
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts';

import type { Visualization } from '../../api/schemas';

const COLORS = ['#3b6fe0', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899', '#84cc16'];

interface Props {
  visualization: Visualization;
  columns: string[];
  rows: unknown[][];
}

function toRecords(columns: string[], rows: unknown[][]): Array<Record<string, unknown>> {
  return rows.map((r) => {
    const o: Record<string, unknown> = {};
    columns.forEach((c, i) => (o[c] = r[i]));
    return o;
  });
}

function firstNumericColumn(columns: string[], rows: unknown[][], exclude?: string | null): string | null {
  for (const c of columns) {
    if (c === exclude) continue;
    const idx = columns.indexOf(c);
    if (rows.length && rows.every((r) => r[idx] == null || typeof r[idx] === 'number')) {
      if (rows.some((r) => typeof r[idx] === 'number')) return c;
    }
  }
  return null;
}

export function ChartRenderer({ visualization, columns, rows }: Props) {
  const { kind } = visualization;
  if (kind === 'table' || rows.length === 0 || columns.length < 2) return null;

  const data = toRecords(columns, rows);
  const x = visualization.x ?? columns[0];
  const y = visualization.y ?? firstNumericColumn(columns, rows, x) ?? columns[1];

  return (
    <div className="h-80 w-full">
      <ResponsiveContainer width="100%" height="100%">
        {kind === 'line' ? (
          <LineChart data={data} margin={{ top: 8, right: 16, left: 4, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey={x} tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Line type="monotone" dataKey={y} stroke={COLORS[0]} strokeWidth={2} dot={false} />
          </LineChart>
        ) : kind === 'bar' ? (
          <BarChart data={data} margin={{ top: 8, right: 16, left: 4, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey={x} tick={{ fontSize: 11 }} interval={0} angle={-20} textAnchor="end" height={60} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Bar dataKey={y} radius={[4, 4, 0, 0]}>
              {data.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        ) : kind === 'pie' ? (
          <PieChart>
            <Tooltip />
            <Legend />
            <Pie data={data} dataKey={y} nameKey={x} outerRadius={110} label>
              {data.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
          </PieChart>
        ) : (
          <ScatterChart margin={{ top: 8, right: 16, left: 4, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey={x} name={x} tick={{ fontSize: 11 }} type="number" />
            <YAxis dataKey={y} name={y} tick={{ fontSize: 11 }} type="number" />
            <ZAxis range={[60, 60]} />
            <Tooltip cursor={{ strokeDasharray: '3 3' }} />
            <Scatter data={data} fill={COLORS[0]} />
          </ScatterChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
