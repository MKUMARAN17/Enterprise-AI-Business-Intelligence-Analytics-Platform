/**
 * Route table.
 *   /sign-in     public sign-in (no chrome)
 *   *            AppLayout shell behind <RequireAuth>
 *     /          → /workspace
 *     /workspace the Ask workspace (prompt → summary/table/chart/export)
 */
import { createBrowserRouter, Navigate, RouterProvider, type RouteObject } from 'react-router-dom';

import { AppLayout } from './AppLayout';
import { RequireAuth } from './auth/RequireAuth';
import { SignInPage } from './pages/sign-in/SignInPage';
import { AskWorkspace } from './pages/workspace/AskWorkspace';

export const routeTable: RouteObject[] = [
  { path: '/sign-in', element: <SignInPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { index: true, element: <Navigate to="/workspace" replace /> },
          { path: 'workspace', element: <AskWorkspace /> },
        ],
      },
    ],
  },
];

const router = createBrowserRouter(routeTable);

export function AppRouter() {
  return <RouterProvider router={router} />;
}
