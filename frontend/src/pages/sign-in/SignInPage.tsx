/**
 * Sign-in page (dev auth mode).
 *
 * Pick a role → the backend mints a token for it (POST /api/v1/dev/login) →
 * session stored → redirect to the originally-requested page (`?next=`) or the
 * workspace. A production build would replace this with the corporate OIDC
 * redirect; the rest of the app is unchanged because auth state lives behind
 * `useAuth`.
 */
import { Sparkles } from 'lucide-react';
import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import { ApiError } from '../../api/client';
import { useAuth } from '../../auth/AuthContext';
import { Button, Card } from '../../components/ui/primitives';
import { env } from '../../config/env';
import { ALL_ROLES, roleLabel, ROLE_SCOPE } from '../../lib/roles';

export function SignInPage() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [role, setRole] = useState<string>(ALL_ROLES[0]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async () => {
    setBusy(true);
    setError(null);
    try {
      await signIn(role);
      const next = params.get('next');
      navigate(next ? decodeURIComponent(next) : '/workspace', { replace: true });
    } catch (e) {
      const msg =
        e instanceof ApiError
          ? `${e.message}${e.status ? ` (${e.status})` : ''}`
          : 'Sign-in failed. Is the backend running with BI_ALLOW_DEV_LOGIN=true?';
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex h-full items-center justify-center bg-slate-50 p-6 dark:bg-slate-950">
      <Card className="w-full max-w-md p-7">
        <div className="mb-5 flex items-center gap-2">
          <Sparkles className="text-brand-600" />
          <div>
            <h1 className="text-lg font-semibold">{env.productName}</h1>
            <p className="text-xs text-slate-500 dark:text-slate-400">AI Business Analyst — sign in</p>
          </div>
        </div>

        <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-200">
          Sign in as
        </label>
        <div className="space-y-2">
          {ALL_ROLES.map((r) => (
            <button
              key={r}
              onClick={() => setRole(r)}
              className={`flex w-full items-center justify-between rounded-lg border px-3 py-2.5 text-left text-sm transition ${
                role === r
                  ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/30'
                  : 'border-slate-200 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/50'
              }`}
            >
              <span className="font-medium">{roleLabel(r)}</span>
              <span className="ml-3 text-xs text-slate-400">{ROLE_SCOPE[r]}</span>
            </button>
          ))}
        </div>

        {error && (
          <p className="mt-4 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:bg-rose-900/30 dark:text-rose-300">
            {error}
          </p>
        )}

        <Button className="mt-5 w-full" onClick={onSubmit} disabled={busy}>
          {busy ? 'Signing in…' : 'Continue'}
        </Button>
        <p className="mt-3 text-center text-xs text-slate-400">
          Dev sign-in — the backend issues a JWT for the selected role.
        </p>
      </Card>
    </div>
  );
}
