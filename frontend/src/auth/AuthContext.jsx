/**
 * Состояние входа: текущий пользователь и его роль.
 *
 * Роль хранится только для того, чтобы не показывать пользователю разделы,
 * которые ему всё равно недоступны. Ограничение прав обеспечивает сервер:
 * скрытая кнопка защитой не является, а проверку роли выполняет зависимость
 * require_role на каждом защищённом маршруте.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import {
  api,
  clearTokens,
  getRefreshToken,
  saveTokens,
  setAccessToken,
  setUnauthorizedHandler,
} from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const forget = useCallback(() => {
    clearTokens();
    setUser(null);
  }, []);

  // Восстановление входа после перезагрузки страницы: токен доступа живёт в
  // памяти вкладки и теряется, токен обновления сохраняется
  useEffect(() => {
    setUnauthorizedHandler(forget);

    async function restore() {
      if (!getRefreshToken()) {
        setLoading(false);
        return;
      }
      try {
        const tokens = await api.post("/api/auth/refresh", {
          refresh_token: getRefreshToken(),
        });
        saveTokens(tokens);
        setUser(await api.get("/api/auth/me"));
      } catch {
        forget();
      } finally {
        setLoading(false);
      }
    }

    restore();
  }, [forget]);

  const login = useCallback(async (email, password) => {
    const tokens = await api.post("/api/auth/login", { email, password });
    saveTokens(tokens);
    setUser(await api.get("/api/auth/me"));
  }, []);

  const acceptTokens = useCallback(async (tokens) => {
    saveTokens(tokens);
    setUser(await api.get("/api/auth/me"));
  }, []);

  const logout = useCallback(async () => {
    const refresh = getRefreshToken();
    try {
      if (refresh) await api.post("/api/auth/logout", { refresh_token: refresh });
    } catch {
      // Сервер мог уже отозвать токен: для пользователя выход всё равно состоялся
    }
    forget();
  }, [forget]);

  const value = useMemo(
    () => ({
      user,
      loading,
      login,
      logout,
      acceptTokens,
      setAccessToken,
      isStaff: user?.role === "moderator" || user?.role === "admin",
      isAdmin: user?.role === "admin",
    }),
    [user, loading, login, logout, acceptTokens],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth вызван вне AuthProvider");
  return context;
}
