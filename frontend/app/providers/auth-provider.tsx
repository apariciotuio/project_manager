'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react';
import type { ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { apiGet, apiPost } from '@/lib/api-client';
import { UnauthenticatedError } from '@/lib/types/auth';
import type { AuthMeResponse, AuthUser } from '@/lib/types/auth';

interface AuthState {
  user: AuthUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      try {
        const response = await apiGet<AuthMeResponse>('/api/v1/auth/me');
        setUser(response.data);
      } catch (err) {
        // UnauthenticatedError or ApiError — user stays null, middleware redirects
        if (!(err instanceof UnauthenticatedError)) {
          // Log unexpected errors but don't crash
          console.error('[AuthProvider] Unexpected error loading user:', err);
        }
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    })();
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiPost('/api/v1/auth/logout', {});
    } catch {
      // Redirect regardless of API failure
    } finally {
      setUser(null);
      router.push('/login');
    }
  }, [router]);

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: user !== null,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (ctx === null) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}
