/**
 * Auth context — the reactive session store for the app.
 *
 * Holds the signed-in `Session` (token + role + username), hydrated from
 * localStorage on boot so a reload keeps you signed in. `signIn` calls the
 * backend dev-login, persists the session, and updates state; `signOut` clears
 * everything. This is the self-contained stand-in for the reference's
 * `@tensaw/ui-runtime` authStore.
 */
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';

import { biApi } from '../api/client';
import { clearSession, getSession, setSession, type Session } from './session';

interface AuthState {
  session: Session | null;
  isAuthenticated: boolean;
  signIn: (role: string) => Promise<void>;
  signOut: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSessionState] = useState<Session | null>(() => getSession());

  const signIn = useCallback(async (role: string) => {
    const res = await biApi.devLogin(role);
    const next: Session = { token: res.token, role: res.role, username: res.username };
    setSession(next);
    setSessionState(next);
  }, []);

  const signOut = useCallback(() => {
    clearSession();
    setSessionState(null);
  }, []);

  const value = useMemo<AuthState>(
    () => ({ session, isAuthenticated: Boolean(session), signIn, signOut }),
    [session, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>');
  return ctx;
}
