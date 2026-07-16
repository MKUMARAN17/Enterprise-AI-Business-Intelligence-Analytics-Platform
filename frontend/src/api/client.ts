/**
 * The one BI API client.
 *
 * A single axios instance carries the bearer token on every request (read from
 * the session store — the reference frontend's dev-token interceptor pattern)
 * and normalises backend RFC-7807-ish problem-details bodies into a typed
 * `ApiError`. A terminal 401 clears the session and hands control to the
 * registered reauth handler (wired in main → routes to /sign-in).
 *
 * Endpoints (see backend enterprise_bi/api):
 *   POST /api/v1/ask         ask a question, get the full analytical answer
 *   POST /api/v1/dev/login   DEV: mint a token for a role (authMode="dev")
 */
import axios, { AxiosError, type AxiosInstance } from 'axios';

import { env } from '../config/env';
import { clearSession, getToken } from '../auth/session';
import {
  AskResponseSchema,
  DevLoginResponseSchema,
  type AskRequest,
  type AskResponse,
  type DevLoginResponse,
} from './schemas';

export class ApiError extends Error {
  constructor(
    message: string,
    readonly code: string | undefined,
    readonly status: number | undefined,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

let onReauthRequired: (reason?: string) => void = () => {};
export function setReauthHandler(fn: (reason?: string) => void): void {
  onReauthRequired = fn;
}

let instance: AxiosInstance | null = null;

function client(): AxiosInstance {
  if (instance) return instance;
  instance = axios.create({ baseURL: env.apiUrl, timeout: 30_000 });

  instance.interceptors.request.use((config) => {
    const token = getToken();
    if (token) config.headers.set('Authorization', `Bearer ${token}`);
    return config;
  });

  instance.interceptors.response.use(
    (r) => r,
    (error: unknown) => {
      const err = error as AxiosError<{ detail?: { code?: string; message?: string } }>;
      const status = err.response?.status;
      if (status === 401) {
        clearSession();
        onReauthRequired('session expired');
      }
      const detail = err.response?.data?.detail;
      const code = detail?.code;
      const message = detail?.message ?? err.message ?? 'Request failed';
      return Promise.reject(new ApiError(message, code, status));
    },
  );

  return instance;
}

export const biApi = {
  /** POST /api/v1/ask — one natural-language turn → full analytical answer. */
  async ask(body: AskRequest): Promise<AskResponse> {
    const res = await client().post<unknown>('/api/v1/ask', body);
    const parsed = AskResponseSchema.safeParse(res.data);
    if (!parsed.success) {
      throw new ApiError('Response did not match the expected schema', 'SCHEMA_MISMATCH', undefined);
    }
    return parsed.data;
  },

  /** POST /api/v1/dev/login — DEV only. Mint a token for a role. */
  async devLogin(role: string, username?: string): Promise<DevLoginResponse> {
    const res = await client().post<unknown>('/api/v1/dev/login', { role, username });
    const parsed = DevLoginResponseSchema.safeParse(res.data);
    if (!parsed.success) {
      throw new ApiError('Login response invalid', 'SCHEMA_MISMATCH', undefined);
    }
    return parsed.data;
  },
};
