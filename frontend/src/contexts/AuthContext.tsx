"use client";

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, getStoredJwt, setStoredJwt } from "@/lib/api";

export interface AuthUser {
  id: number;
  email: string;
  role: "admin" | "user" | "viewer";
  is_active: boolean;
  created_at?: string;
}

interface AuthState {
  user: AuthUser | null;
  loading: boolean;
  // When true, the backend has no users yet, so the app runs in bootstrap mode.
  // In that case we skip the login gate entirely until the first user registers.
  bootstrap: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  // Assume bootstrap until we know otherwise — avoids flashing a login screen
  // on a fresh install where no users exist yet.
  const [bootstrap, setBootstrap] = useState(true);

  const refresh = useCallback(async () => {
    const token = getStoredJwt();
    if (token) {
      try {
        const me = await api.getMe();
        setUser(me);
        setBootstrap(false);
        return;
      } catch {
        setStoredJwt("");
      }
    }
    // No token — ask the backend whether any users exist.
    try {
      const res = await fetch("/api/users/me", {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      // 401 with "Authentication required" means multi-tenancy is ON but we
      // don't have a session. 404 / bootstrap is handled by /auth/status.
      const status = await api.getAuthStatus();
      // If no API keys AND /users/me was 401, bootstrap is still on for
      // first-run installs — treat as single-user mode.
      setBootstrap(status.bootstrap_mode && res.status !== 401);
    } catch {
      setBootstrap(true);
    }
    setUser(null);
  }, []);

  useEffect(() => {
    refresh().finally(() => setLoading(false));
  }, [refresh]);

  const login = useCallback(async (email: string, password: string) => {
    const resp = await api.login(email, password);
    setStoredJwt(resp.access_token);
    setUser(resp.user);
    setBootstrap(false);
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    const resp = await api.register(email, password);
    setStoredJwt(resp.access_token);
    setUser(resp.user);
    setBootstrap(false);
  }, []);

  const logout = useCallback(() => {
    setStoredJwt("");
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, bootstrap, login, register, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
