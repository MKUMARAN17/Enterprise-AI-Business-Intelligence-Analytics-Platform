/**
 * Zod schemas mirroring the backend contract (enterprise_bi/api/models.py).
 * Responses are validated at the client boundary so the UI works against a
 * typed, trusted shape — a schema drift surfaces as a clear error, not a
 * mystery `undefined` deep in a component.
 */
import { z } from 'zod';

export const AskRequestSchema = z.object({
  question: z.string().min(1).max(4000),
  history: z.array(z.object({ question: z.string() })).default([]),
});
export type AskRequest = z.infer<typeof AskRequestSchema>;

const IntentSchema = z
  .object({
    intent: z.string().optional(),
    domain: z.string().optional(),
    metrics: z.array(z.string()).optional(),
    wants_export: z.boolean().optional(),
    wants_dashboard: z.boolean().optional(),
  })
  .passthrough();

const KpiSchema = z
  .object({
    metric: z.string(),
    total: z.number().optional(),
    average: z.number().optional(),
    max: z.number().optional(),
    min: z.number().optional(),
  })
  .passthrough();

const AnalyticsSchema = z
  .object({
    kpis: z.array(KpiSchema).default([]),
    observations: z.array(z.string()).default([]),
    dimensions: z
      .object({
        numeric: z.array(z.string()).default([]),
        temporal: z.array(z.string()).default([]),
        categorical: z.array(z.string()).default([]),
      })
      .partial()
      .optional(),
  })
  .passthrough();

export const VisualizationSchema = z
  .object({
    kind: z.enum(['table', 'line', 'bar', 'pie', 'scatter']).default('table'),
    reason: z.string().default(''),
    spec: z.record(z.unknown()).default({}),
    x: z.string().nullable().default(null),
    y: z.string().nullable().default(null),
  })
  .passthrough();
export type Visualization = z.infer<typeof VisualizationSchema>;

const InsightSchema = z
  .object({
    summary: z.string().default(''),
    highlights: z.array(z.string()).default([]),
    recommendations: z.array(z.string()).default([]),
  })
  .passthrough();

const ExportSchema = z
  .object({
    format: z.string().optional(),
    path: z.string().optional(),
    bytes: z.number().optional(),
    error: z.string().optional(),
  })
  .passthrough();

const ErrorSchema = z
  .object({
    code: z.string(),
    message: z.string(),
    categories: z.array(z.string()).optional(),
  })
  .passthrough();

export const AskResponseSchema = z.object({
  request_id: z.string().nullable().optional(),
  status: z.string(),
  intent: IntentSchema.nullable().optional(),
  generated_sql: z.string().nullable().optional(),
  columns: z.array(z.string()).default([]),
  rows: z.array(z.array(z.unknown())).default([]),
  row_count: z.number().default(0),
  analytics: AnalyticsSchema.default({ kpis: [], observations: [] }),
  visualization: VisualizationSchema.optional(),
  insight: InsightSchema.default({ summary: '', highlights: [], recommendations: [] }),
  export: ExportSchema.nullable().optional(),
  execution_ms: z.number().nullable().optional(),
  error: ErrorSchema.nullable().optional(),
});
export type AskResponse = z.infer<typeof AskResponseSchema>;

export const DevLoginResponseSchema = z.object({
  token: z.string(),
  role: z.string(),
  username: z.string(),
});
export type DevLoginResponse = z.infer<typeof DevLoginResponseSchema>;
