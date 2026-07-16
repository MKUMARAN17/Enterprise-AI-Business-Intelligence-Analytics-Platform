/**
 * Session token storage.
 *
 * The dev token lives in `localStorage` so a page reload keeps you signed in
 * (this is the dev ergonomics seam — a production OIDC build would hold the
 * token in memory + httpOnly cookie instead). The axios interceptor reads
 * `getToken()` on every request; the sign-in flow writes it via `setSession`.
 */
const TOKEN_KEY = 'bi.token';
const ROLE_KEY = 'bi.role';
const USER_KEY = 'bi.username';

export interface Session {
  token: string;
  role: string;
  username: string;
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getSession(): Session | null {
  const token = localStorage.getItem(TOKEN_KEY);
  const role = localStorage.getItem(ROLE_KEY);
  const username = localStorage.getItem(USER_KEY);
  if (!token || !role || !username) return null;
  return { token, role, username };
}

export function setSession(s: Session): void {
  localStorage.setItem(TOKEN_KEY, s.token);
  localStorage.setItem(ROLE_KEY, s.role);
  localStorage.setItem(USER_KEY, s.username);
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ROLE_KEY);
  localStorage.removeItem(USER_KEY);
}
