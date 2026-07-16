/**
 * Light/dark theme provider. Stamps `data-theme` on <html> (the CSS + Tailwind
 * `darkMode` selector key off it) and persists the choice. Mirrors the
 * reference `AppTheme`.
 */
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

type Mode = 'light' | 'dark';
interface ThemeState {
  mode: Mode;
  toggleMode: () => void;
}

const ThemeContext = createContext<ThemeState | null>(null);
const KEY = 'bi.theme';

export function AppThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<Mode>(() => (localStorage.getItem(KEY) as Mode) || 'light');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', mode);
    localStorage.setItem(KEY, mode);
  }, [mode]);

  const value = useMemo<ThemeState>(
    () => ({ mode, toggleMode: () => setMode((m) => (m === 'light' ? 'dark' : 'light')) }),
    [mode],
  );
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useAppTheme(): ThemeState {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useAppTheme must be used within <AppThemeProvider>');
  return ctx;
}
