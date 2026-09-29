import axios from "axios";

const BASE = `${import.meta.env.VITE_API_BASE || ""}/api/v1`;
const TOKENS_KEY = "alnoor.tokens";

export function getTokens() {
  try {
    return JSON.parse(localStorage.getItem(TOKENS_KEY)) || null;
  } catch {
    return null;
  }
}

export function setTokens(tokens) {
  try {
    if (tokens) localStorage.setItem(TOKENS_KEY, JSON.stringify(tokens));
    else localStorage.removeItem(TOKENS_KEY);
  } catch {
    /* storage unavailable (private mode) — session will not persist */
  }
}

export const api = axios.create({ baseURL: BASE });

api.interceptors.request.use((config) => {
  const t = getTokens();
  if (t?.access) config.headers.Authorization = `Bearer ${t.access}`;
  return config;
});

let refreshing = null;
let onLoggedOut = () => {};
export function setLogoutHandler(fn) {
  onLoggedOut = fn;
}

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config;
    const t = getTokens();
    if (error.response?.status === 401 && t?.refresh && !original._retry && !original.url.includes("/auth/")) {
      original._retry = true;
      try {
        refreshing =
          refreshing ||
          axios.post(`${BASE}/auth/refresh/`, { refresh: t.refresh }).finally(() => {
            refreshing = null;
          });
        const { data } = await refreshing;
        setTokens({ access: data.access, refresh: data.refresh || t.refresh });
        original.headers.Authorization = `Bearer ${data.access}`;
        return api(original);
      } catch {
        setTokens(null);
        onLoggedOut();
      }
    }
    return Promise.reject(error);
  },
);

/** Human-readable message from our {detail, errors} error format. */
export function errorMessage(err) {
  const data = err?.response?.data;
  if (!data) return err?.message || "Network error — is the server running?";
  if (data instanceof Blob) return "Request failed.";
  if (typeof data === "string") return data.slice(0, 200);
  const parts = [data.detail];
  if (data.errors && typeof data.errors === "object") {
    for (const [field, msgs] of Object.entries(data.errors)) {
      const text = Array.isArray(msgs) ? msgs.map((m) => (typeof m === "object" ? JSON.stringify(m) : m)).join(" ") : JSON.stringify(msgs);
      if (field !== "non_field_errors" && !String(data.detail).includes(text)) parts.push(`${field}: ${text}`);
    }
  }
  return parts.filter(Boolean).join(" • ");
}

/** Field errors map for forms. */
export function fieldErrors(err) {
  const errs = err?.response?.data?.errors || {};
  const out = {};
  for (const [k, v] of Object.entries(errs)) out[k] = Array.isArray(v) ? v.join(" ") : String(v);
  return out;
}

/** Open an HTML print view (receipt, tag, statement) that needs the auth header. */
export async function openPrintable(path, params = {}) {
  const win = window.open("", "_blank");
  if (win) win.document.write("<p style='font-family:sans-serif;padding:20px'>Loading…</p>");
  try {
    const { data } = await api.get(path, { params, responseType: "text" });
    if (!win) return;
    win.document.open();
    win.document.write(data);
    win.document.close();
  } catch (e) {
    if (win) win.document.body.innerHTML = `<p style="color:#b00;font-family:sans-serif;padding:20px">${errorMessage(e)}</p>`;
  }
}

/** Download a file (xlsx/csv) that needs the auth header. */
export async function download(path, params = {}, fallbackName = "export") {
  const res = await api.get(path, { params, responseType: "blob" });
  const cd = res.headers["content-disposition"] || "";
  const match = cd.match(/filename="?([^"]+)"?/);
  const url = URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = match ? match[1] : fallbackName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
