import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import './index.css';
import { AppThemeProvider } from './AppTheme';
import { setReauthHandler } from './api/client';
import { AuthProvider } from './auth/AuthContext';
import { AppRouter } from './routes';

// On a terminal 401 the api client clears the session; send the user to sign-in.
setReauthHandler(() => {
  if (window.location.pathname !== '/sign-in') window.location.assign('/sign-in');
});

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
});

const rootEl = document.getElementById('root');
if (!rootEl) throw new Error('Root element #root not found');

createRoot(rootEl).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AppThemeProvider>
        <AuthProvider>
          <AppRouter />
        </AuthProvider>
      </AppThemeProvider>
    </QueryClientProvider>
  </StrictMode>,
);
