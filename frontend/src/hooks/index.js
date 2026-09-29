import { createContext, useContext, useEffect, useRef, useState } from "react";
import { useApi } from "../api/hooks";

export const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

/** Permission flags from /auth/me/ (see backend core/serializers.permissions_for). */
export function usePermissions() {
  const { user } = useAuth() || {};
  return user?.permissions || {};
}

export function useRole() {
  return useAuth()?.user?.role;
}

export function useGoldRate() {
  const q = useApi("/gold-rates/today/", null, { staleTime: 60_000 });
  return { ...q, rate: q.data?.rate, isToday: q.data?.is_today };
}

export function useSettings() {
  return useApi("/settings/", null, { staleTime: 5 * 60_000 });
}

export function useDebounce(value, delay = 250) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return v;
}

/** Global keyboard shortcuts: { "alt+n": fn, "/": fn } */
export function useHotkeys(map) {
  const ref = useRef(map);
  ref.current = map;
  useEffect(() => {
    const onKey = (e) => {
      const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName);
      const key = `${e.altKey ? "alt+" : ""}${e.ctrlKey ? "ctrl+" : ""}${e.key.toLowerCase()}`;
      const fn = ref.current[key];
      if (!fn) return;
      if (typing && !e.altKey && !e.ctrlKey) return;
      e.preventDefault();
      fn(e);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}

/** Simple persisted UI preference (per browser). */
export function useLocalState(key, initial) {
  const [v, setV] = useState(() => {
    try {
      const s = localStorage.getItem(key);
      return s === null ? initial : JSON.parse(s);
    } catch {
      return initial;
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(v));
    } catch {
      /* ignore */
    }
  }, [key, v]);
  return [v, setV];
}
