/**
 * Route guard — redirects unauthenticated users to /sign-in, preserving where
 * they were headed via a `?next=` param so they land back there after signing
 * in. Mirrors the reference `RequireAuth`.
 */
import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { useAuth } from './AuthContext';

export function RequireAuth() {
  const { isAuthenticated } = useAuth();
  const location = useLocation();
  if (!isAuthenticated) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/sign-in?next=${next}`} replace />;
  }
  return <Outlet />;
}
