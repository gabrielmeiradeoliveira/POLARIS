import React, { createContext, useContext, useState } from "react";

interface AuthUser {
  username: string;
  role: string;
  tokenId?: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("polaris-auth-token"));
  const [user, setUser] = useState<AuthUser | null>(() => {
    const raw = localStorage.getItem("polaris-auth-user");
    return raw ? (JSON.parse(raw) as AuthUser) : null;
  });

  const login = async (username: string, password: string) => {
    const res = await fetch("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const u: AuthUser = { username: data.username, role: data.role, tokenId: data.token_id };
    localStorage.setItem("polaris-auth-token", data.token);
    localStorage.setItem("polaris-auth-user", JSON.stringify(u));
    setToken(data.token);
    setUser(u);
  };

  const logout = async () => {
    if (user?.tokenId) {
      await fetch(`/api/v1/auth/logout?token_id=${encodeURIComponent(user.tokenId)}`, { method: "POST" }).catch(() => {});
    }
    localStorage.removeItem("polaris-auth-token");
    localStorage.removeItem("polaris-auth-user");
    setToken(null);
    setUser(null);
  };

  return <AuthContext.Provider value={{ user, token, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
