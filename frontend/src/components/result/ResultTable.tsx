/** Scrollable result table (UPPERCASE column headers straight from the DB). */
import { Card, CardHeader } from '../ui/primitives';

interface Props {
  columns: string[];
  rows: unknown[][];
  rowCount: number;
}

function fmt(v: unknown): string {
  if (v == null) return '—';
  if (typeof v === 'number') return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
  return String(v);
}

export function ResultTable({ columns, rows, rowCount }: Props) {
  if (columns.length === 0) return null;
  return (
    <Card>
      <CardHeader title="Data" subtitle={`${rowCount} row${rowCount === 1 ? '' : 's'}`} />
      <div className="max-h-96 overflow-auto">
        <table className="w-full border-collapse text-sm">
          <thead className="sticky top-0 bg-slate-50 dark:bg-slate-800">
            <tr>
              {columns.map((c) => (
                <th
                  key={c}
                  className="whitespace-nowrap border-b border-slate-200 px-4 py-2 text-left font-semibold text-slate-600 dark:border-slate-700 dark:text-slate-300"
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, ri) => (
              <tr key={ri} className="odd:bg-white even:bg-slate-50/50 dark:odd:bg-slate-900 dark:even:bg-slate-800/30">
                {columns.map((_, ci) => (
                  <td
                    key={ci}
                    className="whitespace-nowrap border-b border-slate-100 px-4 py-2 text-slate-700 dark:border-slate-800 dark:text-slate-200"
                  >
                    {fmt(r[ci])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
