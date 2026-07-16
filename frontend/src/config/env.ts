/**
 * Typed access to the Vite env — centralised so the rest of the app never
 * touches `import.meta.env` directly (mirrors the reference frontend's
 * `config/env.ts`). Adapted to this project's env var names.
 */
export type AuthMode = 'dev';

export const env = {
  /** Backend base URL for the axios client. Empty ⇒ same-origin. */
  apiUrl: (import.meta.env.VITE_API_BASE_URL as string) ?? 'http://localhost:8000',

  /**
   * Auth mode. Only "dev" is supported in this starter: the backend's
   * POST /api/v1/dev/login mints an HS256 token for a chosen role (gated by
   * BI_ALLOW_DEV_LOGIN). A real deployment would add a "cognito"/OIDC mode.
   */
  authMode: (import.meta.env.VITE_AUTH_MODE as AuthMode) ?? 'dev',

  productName: (import.meta.env.VITE_PRODUCT_NAME as string) ?? 'Enterprise BI',
  isDev: import.meta.env.DEV,
} as const;
