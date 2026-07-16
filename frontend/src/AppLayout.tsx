/**
 * AppLayout — top-level chrome (top bar + side nav + main outlet) wrapping every
 * routed page. Self-contained equivalent of the reference `AppLayout` (which
 * composed the proprietary design-system AppShell/TopNav/SideNav).
 */
import { LogOut, Moon, Shield, Sparkles, Sun } from 'lucide-react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';

import { useAppTheme } from './AppTheme';
import { useAuth } from './auth/AuthContext';
import { Badge } from './components/ui/primitives';
import { env } from './config/env';
import { roleLabel, ROLE_SCOPE } from './lib/roles';

export function AppLayout() {
  const navigate = useNavigate();
  const { session, signOut } = useAuth();
  const { mode, toggleMode } = useAppTheme();

  const handleSignOut = () => {
    signOut();
    navigate('/sign-in');
  };

  return (
    <div className="flex h-full flex-col">
      {/* Top bar */}
      <header className="flex h-14 items-center justify-between border-b border-slate-200 bg-white px-4 dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-center gap-2">
          <Sparkles size={18} className="text-brand-600" />
          <span className="text-base font-semibold tracking-tight">{env.productName}</span>
          <span className="ml-1 text-xs text-slate-400">AI Business Analyst</span>
        </div>
        <div className="flex items-center gap-3">
          {session && (
            <div className="hidden items-center gap-2 sm:flex">
              <Badge tone="blue">{roleLabel(session.role)}</Badge>
              <span className="text-sm text-slate-500 dark:text-slate-400">{session.username}</span>
            </div>
          )}
          <button
            onClick={toggleMode}
            className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
            aria-label="Toggle theme"
          >
            {mode === 'light' ? <Moon size={16} /> : <Sun size={16} />}
          </button>
          <button
            onClick={handleSignOut}
            className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            <LogOut size={15} /> Sign out
          </button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Side nav */}
        <aside className="hidden w-60 flex-shrink-0 border-r border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900 md:block">
          <nav className="space-y-1">
            <NavLink
              to="/workspace"
              className={({ isActive }) =>
                `flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ${
                  isActive
                    ? 'bg-brand-50 text-brand-700 dark:bg-brand-900/30 dark:text-brand-100'
                    : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
                }`
              }
            >
              <Sparkles size={16} /> Ask
            </NavLink>
          </nav>

          {session && (
            <div className="mt-6 rounded-lg border border-slate-200 p-3 text-xs dark:border-slate-800">
              <div className="mb-1 flex items-center gap-1.5 font-semibold text-slate-700 dark:text-slate-200">
                <Shield size={13} /> Data access
              </div>
              <p className="text-slate-500 dark:text-slate-400">{ROLE_SCOPE[session.role] ?? '—'}</p>
            </div>
          )}
        </aside>

        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
