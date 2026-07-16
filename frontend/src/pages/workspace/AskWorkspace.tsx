/**
 * Ask workspace — the product.
 *
 * A prompt box (with sample questions) → POST /api/v1/ask → the assembled answer:
 * business insight + KPI cards, the chosen chart, the data table, an export
 * badge, and the (collapsible) generated SQL. Blocked prompts (guardrail /
 * SQL-guard / RBAC) and errors render as clear banners — the backend's layered
 * safety is surfaced honestly, not hidden.
 *
 * Conversation history is kept client-side and sent with each turn so follow-ups
 * ("now filter to Kerala") have context, matching the backend's `history` input.
 */
import { useMutation } from '@tanstack/react-query';
import { AlertTriangle, Clock, Download, Send, ShieldAlert } from 'lucide-react';
import { useState } from 'react';

import { ApiError, biApi } from '../../api/client';
import type { AskResponse } from '../../api/schemas';
import { ChartRenderer } from '../../components/result/ChartRenderer';
import { InsightPanel, KpiCards } from '../../components/result/InsightPanel';
import { ResultTable } from '../../components/result/ResultTable';
import { SqlPanel } from '../../components/result/SqlPanel';
import { Badge, Button, Card, CardHeader, Spinner } from '../../components/ui/primitives';

const SAMPLES = [
  'Show total collections by branch',
  'Show revenue trend over the last months',
  'Compare employee performance for Q1 and Q2',
  'Which branches are underperforming?',
  'Show customer collections for Kerala and export as Excel',
];

export function AskWorkspace() {
  const [question, setQuestion] = useState('');
  const [history, setHistory] = useState<{ question: string }[]>([]);
  const [result, setResult] = useState<AskResponse | null>(null);

  const mutation = useMutation({
    mutationFn: (q: string) => biApi.ask({ question: q, history }),
    onSuccess: (res, q) => {
      setResult(res);
      setHistory((h) => [...h, { question: q }].slice(-5));
    },
  });

  const submit = (q: string) => {
    const text = q.trim();
    if (!text || mutation.isPending) return;
    setQuestion(text);
    mutation.mutate(text);
  };

  const blocked = result?.status === 'BLOCKED';
  const errored = result?.status === 'ERROR' || (mutation.isError && !result);
  const ok = result?.status === 'OK';
  const viz = result?.visualization;

  return (
    <div className="mx-auto max-w-5xl space-y-5 p-5 sm:p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Ask your data</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Ask a business question in plain English. No SQL required.
        </p>
      </div>

      {/* Prompt box */}
      <Card className="p-4">
        <div className="flex items-end gap-3">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) submit(question);
            }}
            rows={2}
            placeholder="e.g. Show collection performance for the last six months"
            className="min-h-[52px] flex-1 resize-none rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-brand-500 dark:border-slate-700 dark:bg-slate-900"
          />
          <Button onClick={() => submit(question)} disabled={mutation.isPending || !question.trim()}>
            <Send size={15} /> Ask
          </Button>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {SAMPLES.map((s) => (
            <button
              key={s}
              onClick={() => submit(s)}
              disabled={mutation.isPending}
              className="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-600 hover:border-brand-400 hover:text-brand-700 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300"
            >
              {s}
            </button>
          ))}
        </div>
      </Card>

      {mutation.isPending && (
        <Card className="p-6">
          <Spinner label="Thinking — classifying intent, retrieving schema, generating & validating SQL…" />
        </Card>
      )}

      {/* Blocked (guardrail / SQL-guard / RBAC) */}
      {blocked && result?.error && (
        <Card className="border-rose-200 p-5 dark:border-rose-900">
          <div className="flex items-start gap-3">
            <ShieldAlert className="mt-0.5 flex-shrink-0 text-rose-600" size={18} />
            <div>
              <h3 className="text-sm font-semibold text-rose-700 dark:text-rose-300">Request blocked</h3>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{result.error.message}</p>
              <Badge tone="red">{result.error.code}</Badge>
            </div>
          </div>
        </Card>
      )}

      {/* Error */}
      {errored && (
        <Card className="border-amber-200 p-5 dark:border-amber-900">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 flex-shrink-0 text-amber-600" size={18} />
            <div>
              <h3 className="text-sm font-semibold text-amber-700 dark:text-amber-300">Something went wrong</h3>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
                {result?.error?.message ??
                  (mutation.error instanceof ApiError ? mutation.error.message : 'Request failed.')}
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* Success */}
      {ok && result && (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
            <Badge tone="green">OK</Badge>
            {result.intent?.domain && <Badge tone="blue">{result.intent.domain}</Badge>}
            {viz?.kind && <Badge>chart: {viz.kind}</Badge>}
            {result.execution_ms != null && (
              <span className="flex items-center gap-1">
                <Clock size={12} /> {result.execution_ms} ms
              </span>
            )}
            {result.export && (
              <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                <Download size={12} />
                {result.export.error ? `export: ${result.export.error}` : `export ready (${result.export.format})`}
              </span>
            )}
          </div>

          <KpiCards analytics={result.analytics} />
          <InsightPanel insight={result.insight} />

          {viz && viz.kind !== 'table' && result.rows.length > 0 && (
            <Card>
              <CardHeader title="Visualization" subtitle={viz.reason} />
              <div className="p-4">
                <ChartRenderer visualization={viz} columns={result.columns} rows={result.rows} />
              </div>
            </Card>
          )}

          <ResultTable columns={result.columns} rows={result.rows} rowCount={result.row_count} />
          <SqlPanel sql={result.generated_sql} />
        </div>
      )}
    </div>
  );
}
