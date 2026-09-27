import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { authApi, setTokenRenewedHandler } from "../api/webapp";
import type { ApiKeyLoginMode, UserProfile } from "../types/webapp";
import { getStoredInitData } from "../telegramInit";

const STORAGE_KEY = "webapp_session";

interface AuthContextType {
  sessionToken: string | null;
  initData: string | null;
  isTelegram: boolean;
  isAuthenticated: boolean;
  user: UserProfile | null;
  setToken: (token: string | null) => void;
  setUser: (user: UserProfile | null) => void;
  refreshUser: () => Promise<UserProfile | null>;
  clearSession: () => void;
  loading: boolean;
  apiKeyLoginMode: ApiKeyLoginMode;
}

const AuthContext = createContext<AuthContextType | null>(null);

function readInitData(): string | null {
  const stored = getStoredInitData();
  if (stored) return stored;
  return (typeof window !== "undefined" && window.Telegram?.WebApp?.initData) || null;
}

function isSessionExpiredError(message: string): boolean {
  return message.includes("منقضی") || message.includes("توکن");
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [initData, setInitData] = useState<string | null>(null);
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [apiKeyLoginMode, setApiKeyLoginMode] = useState<ApiKeyLoginMode>("none");

  const isTelegram = !!initData;
  const isAuthenticated = !!sessionToken || !!initData;

  const setToken = useCallback((token: string | null) => {
    if (token) {
      localStorage.setItem(STORAGE_KEY, token);
      setSessionToken(token);
    } else {
      localStorage.removeItem(STORAGE_KEY);
      setSessionToken(null);
    }
  }, []);

  const clearSession = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setSessionToken(null);
    setUser(null);
  }, []);

  const refreshUser = useCallback(async (): Promise<UserProfile | null> => {
    try {
      if (initData) {
        const res = await authApi.getInfoWithInitData(initData);
        setApiKeyLoginMode(res.api_key_login_mode);
        if (res.user) {
          setUser(res.user);
          return res.user;
        }
        setUser(null);
        return null;
      }
      if (sessionToken) {
        const res = await authApi.getInfoSession(sessionToken);
        setApiKeyLoginMode(res.api_key_login_mode);
        if (res.user) {
          setUser(res.user);
          return res.user;
        }
        clearSession();
        return null;
      }
      return null;
    } catch (err) {
      const message = err instanceof Error ? err.message : "";
      if (sessionToken && isSessionExpiredError(message)) {
        clearSession();
      } else if (sessionToken) {
        clearSession();
      } else {
        setUser(null);
      }
      return null;
    }
  }, [initData, sessionToken, clearSession]);

  useEffect(() => {
    let active = true;

    let data = readInitData();
    if (data) {
      if (!active) return;
      setInitData(data);
      window.Telegram?.WebApp?.ready?.();
      window.Telegram?.WebApp?.expand?.();
      setLoading(false);
      return;
    }

    const token = localStorage.getItem(STORAGE_KEY);
    if (token) {
      if (!active) return;
      setSessionToken(token);
      setLoading(false);
      return;
    }

    const ua = navigator.userAgent.toLowerCase();
    const inTg = ua.includes("telegram") || !!window.Telegram?.WebApp;
    if (!inTg) {
      if (!active) return;
      setLoading(false);
      return;
    }

    const t = setTimeout(() => {
      if (!active) return;
      data = readInitData();
      if (data) {
        setInitData(data);
        window.Telegram?.WebApp?.ready?.();
        window.Telegram?.WebApp?.expand?.();
      }
      setLoading(false);
    }, 150);
    return () => {
      active = false;
      clearTimeout(t);
    };
  }, []);

  useEffect(() => {
    if (loading || !isAuthenticated) return;
    void refreshUser();
  }, [loading, isAuthenticated, refreshUser]);

  useEffect(() => {
    // Backend slides an active session's expiry forward via this header;
    // persist it so activity keeps the user logged in without a hard 14-day cliff.
    setTokenRenewedHandler(setToken);
    return () => setTokenRenewedHandler(null);
  }, [setToken]);

  return (
    <AuthContext.Provider
      value={{
        sessionToken,
        initData,
        isTelegram,
        isAuthenticated,
        user,
        setToken,
        setUser,
        refreshUser,
        clearSession,
        loading,
        apiKeyLoginMode,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
