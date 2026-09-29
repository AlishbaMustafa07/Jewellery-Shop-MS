import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";

function clean(params) {
  const out = {};
  for (const [k, v] of Object.entries(params || {})) {
    if (v !== "" && v !== null && v !== undefined) out[k] = v;
  }
  return out;
}

/** GET a resource. `path` null disables the query. */
export function useApi(path, params, options = {}) {
  return useQuery({
    queryKey: [path, clean(params)],
    queryFn: async () => (await api.get(path, { params: clean(params) })).data,
    enabled: !!path,
    placeholderData: keepPreviousData,
    ...options,
  });
}

/** POST/PATCH/DELETE; invalidates the given query-key prefixes on success. */
export function useApiMutation(method, path, { invalidate = [], ...options } = {}) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars) => {
      const url = typeof path === "function" ? path(vars) : path;
      const body = vars && vars.__body !== undefined ? vars.__body : vars;
      return (await api.request({ method, url, data: body })).data;
    },
    onSuccess: (...args) => {
      const keys = invalidate.length ? invalidate : [];
      keys.forEach((k) => qc.invalidateQueries({ predicate: (q) => String(q.queryKey[0]).startsWith(k) }));
      options.onSuccess?.(...args);
    },
    ...Object.fromEntries(Object.entries(options).filter(([k]) => k !== "onSuccess")),
  });
}

export function useInvalidate() {
  const qc = useQueryClient();
  return (...prefixes) =>
    prefixes.forEach((k) => qc.invalidateQueries({ predicate: (q) => String(q.queryKey[0]).startsWith(k) }));
}
