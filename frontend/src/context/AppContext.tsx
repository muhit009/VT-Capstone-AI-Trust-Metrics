import { createContext, useContext, useState, ReactNode } from 'react';

// ── Types ─────────────────────────────────────────────────────────────────────

interface AppState {
  isLoading: boolean;
  error: string | null;
}

interface AppContextValue extends AppState {
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

// ── Context ───────────────────────────────────────────────────────────────────

const AppContext = createContext<AppContextValue | null>(null);

// ── Provider ──────────────────────────────────────────────────────────────────

export function AppProvider({ children }: { children: ReactNode }) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const value: AppContextValue = {
    isLoading,
    error,
    setLoading: setIsLoading,
    setError,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useAppContext(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) {
    throw new Error('useAppContext must be used within an AppProvider');
  }
  return ctx;
}
