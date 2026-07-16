/** The business narrative + KPI cards produced by the Analytics + Insight agents. */
import { Lightbulb, TrendingUp } from 'lucide-react';

import type { AskResponse } from '../../api/schemas';
import { Card, CardHeader } from '../ui/primitives';

function fmtNum(v: number | undefined): string {
  if (v == null) return '—';
  return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export function KpiCards({ analytics }: { analytics: AskResponse['analytics'] }) {
  const kpis = analytics.kpis ?? [];
  if (kpis.length === 0) return null;
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {kpis.map((k) => (
        <Card key={k.metric} className="p-4">
          <p className="truncate text-xs font-medium uppercase tracking-wide text-slate-400">{k.metric}</p>
          <p className="mt-1 text-xl font-semibold text-slate-800 dark:text-slate-100">{fmtNum(k.total)}</p>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            avg {fmtNum(k.average)} · max {fmtNum(k.max)}
          </p>
        </Card>
      ))}
    </div>
  );
}

export function InsightPanel({ insight }: { insight: AskResponse['insight'] }) {
  if (!insight?.summary && (insight?.highlights?.length ?? 0) === 0) return null;
  return (
    <Card>
      <CardHeader title="Business insight" right={<TrendingUp size={16} className="text-brand-600" />} />
      <div className="space-y-3 p-5">
        {insight.summary && <p className="text-sm leading-relaxed text-slate-700 dark:text-slate-200">{insight.summary}</p>}
        {insight.highlights?.length > 0 && (
          <ul className="space-y-1.5">
            {insight.highlights.map((h, i) => (
              <li key={i} className="flex gap-2 text-sm text-slate-600 dark:text-slate-300">
                <span className="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-brand-500" />
                {h}
              </li>
            ))}
          </ul>
        )}
        {insight.recommendations?.length > 0 && (
          <div className="rounded-lg bg-amber-50 p-3 dark:bg-amber-900/20">
            <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-amber-700 dark:text-amber-300">
              <Lightbulb size={13} /> Recommendations
            </div>
            <ul className="space-y-1">
              {insight.recommendations.map((r, i) => (
                <li key={i} className="text-sm text-amber-800 dark:text-amber-200">
                  {r}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Card>
  );
}
