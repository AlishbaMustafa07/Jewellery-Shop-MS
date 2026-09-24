import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, getTokens, setLogoutHandler, setTokens } from "../../api/client";
import { AuthContext } from "../../hooks";

export default function AuthProvider({ children }) {
  const qc = useQueryClient();
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  const logout = useCallback(async () => {
    const t = getTokens();
    try {
      if (t?.refresh) await api.post("/auth/logout/", { refresh: t.refresh });
    } catch {
      /* token may already be invalid */
    }
    setTokens(null);
    setUser(null);
    qc.clear();
  }, [qc]);

  useEffect(() => {
    setLogoutHandler(() => {
      setUser(null);
      qc.clear();
    });
    if (!getTokens()) {
      setReady(true);
      return;
    }
    api
      .get("/auth/me/")
      .then((r) => setUser(r.data))
      .catch(() => setTokens(null))
      .finally(() => setReady(true));
  }, [qc]);

  const login = useCallback(async (username, password) => {
    const { data } = await api.post("/auth/login/", { username, password });
    setTokens({ access: data.access, refresh: data.refresh });
    setUser(data.user);
    return data.user;
  }, []);

  const refreshMe = useCallback(async () => {
    const { data } = await api.get("/auth/me/");
    setUser(data);
  }, []);

  const value = useMemo(() => ({ user, ready, login, logout, refreshMe }), [user, ready, login, logout, refreshMe]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
