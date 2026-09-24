import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { download, errorMessage, openPrintable } from "../api/client";
import { label as labelize } from "../utils/format";

/* ---------------- Toasts ---------------- */
const ToastCtx = createContext(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const push = useCallback((message, kind = "ok") => {
    const id = Math.random();
    setToasts((t) => [...t, { id, message, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), kind === "error" ? 7000 : 3500);
  }, []);
  const api = useMemo(
    () =>
      Object.assign((m, k) => push(m, k), {
        ok: (m) => push(m, "ok"),
        error: (e) => push(typeof e === "string" ? e : errorMessage(e), "error"),
      }),
    [push],
  );
  return (
    <ToastCtx.Provider value={api}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.kind}`}>{t.message}</div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

/* ---------------- Basics ---------------- */
export function Button({ variant = "", size = "", className = "", ...props }) {
  return <button type="button" className={`btn ${variant} ${size} ${className}`} {...props} />;
}

export function Card({ title, actions, children, className = "", bodyClass = "card-body" }) {
  return (
    <div className={`card ${className}`}>
      {(title || actions) && (
        <div className="card-head">
          {typeof title === "string" ? <h3>{title}</h3> : title}
          <div className="spacer" />
          {actions}
        </div>
      )}
      <div className={bodyClass}>{children}</div>
    </div>
  );
}

export function Stat({ label, value, hint }) {
  return (
    <div className="card stat">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {hint && <div className="hint">{hint}</div>}
    </div>
  );
}

export function PageHead({ title, subtitle, children }) {
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {subtitle && <div className="muted small">{subtitle}</div>}
      </div>
      <div className="actions">{children}</div>
    </div>
  );
}

const STATUS_KIND = {
  in_stock: "ok", paid: "ok", returned: "info", refined: "ok", open: "warn", partial: "warn", pending: "warn",
  sold: "accent", voided: "danger", sr_refine: "info", sent_to_refine: "info", sent: "info", transferred: "info",
};
export function Badge({ children, kind }) {
  const k = kind || STATUS_KIND[children] || "";
  return <span className={`badge ${k}`}>{labelize(children)}</span>;
}

export function Alert({ kind = "info", children }) {
  if (!children) return null;
  return <div className={`alert ${kind}`}>{children}</div>;
}

export function ErrorBox({ error }) {
  if (!error) return null;
  return <Alert kind="error">{errorMessage(error)}</Alert>;
}

export function Loading({ what = "Loading" }) {
  return <div className="empty">{what}…</div>;
}

/* ---------------- Form fields ---------------- */
export function Field({ label, error, children, className = "", hint }) {
  return (
    <label className={`field ${className}`}>
      {label && <span className="lbl">{label}</span>}
      {children}
      {hint && !error && <span className="small muted">{hint}</span>}
      {error && <span className="err">{error}</span>}
    </label>
  );
}

export function Input({ label, error, className, hint, ...props }) {
  return (
    <Field label={label} error={error} className={className} hint={hint}>
      <input {...props} value={props.value ?? ""} />
    </Field>
  );
}

export function NumInput({ label, error, className, hint, ...props }) {
  return (
    <Field label={label} error={error} className={className} hint={hint}>
      <input type="number" step="any" inputMode="decimal" className="num" {...props} value={props.value ?? ""}
        onWheel={(e) => e.currentTarget.blur()} />
    </Field>
  );
}

export function Select({ label, error, options, className, placeholder, hint, ...props }) {
  return (
    <Field label={label} error={error} className={className} hint={hint}>
      <select {...props} value={props.value ?? ""}>
        {placeholder !== undefined && <option value="">{placeholder}</option>}
        {options.map((o) =>
          typeof o === "string" ? (
            <option key={o} value={o}>{labelize(o)}</option>
          ) : (
            <option key={o.value} value={o.value}>{o.label}</option>
          ),
        )}
      </select>
    </Field>
  );
}

export function TextArea({ label, error, className, ...props }) {
  return (
    <Field label={label} error={error} className={className}>
      <textarea {...props} value={props.value ?? ""} />
    </Field>
  );
}

/** Small form-state helper: const f = useForm({a: 1}); f.bind("a") */
export function useForm(initial) {
  const [values, setValues] = useState(initial);
  const [errors, setErrors] = useState({});
  const set = (k, v) => setValues((s) => ({ ...s, [k]: v }));
  const bind = (k, type) => ({
    name: k,
    value: values[k] ?? "",
    onChange: (e) => set(k, type === "checkbox" ? e.target.checked : e.target.value),
    error: errors[k],
  });
  return { values, setValues, set, bind, errors, setErrors, reset: () => setValues(initial) };
}

/* ---------------- Modal ---------------- */
export function Modal({ title, onClose, children, footer, wide }) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose?.();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="modal-back" onMouseDown={(e) => e.target === e.currentTarget && onClose?.()}>
      <div className={`modal ${wide ? "wide" : ""}`} role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal-head">
          <h2>{title}</h2>
          <div className="spacer" />
          <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close">✕</Button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  );
}

export function ConfirmReason({ title, prompt, confirmLabel = "Confirm", onConfirm, onClose, busy }) {
  const [reason, setReason] = useState("");
  return (
    <Modal title={title} onClose={onClose} footer={
      <>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="danger solid" disabled={!reason.trim() || busy} onClick={() => onConfirm(reason)}>
          {busy ? "Working…" : confirmLabel}
        </Button>
      </>
    }>
      <p>{prompt}</p>
      <TextArea label="Reason (required)" value={reason} onChange={(e) => setReason(e.target.value)} autoFocus />
    </Modal>
  );
}

/* ---------------- Tabs ---------------- */
export function Tabs({ tabs, value, onChange }) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((t) => (
        <button key={t.value} role="tab" aria-selected={value === t.value} className={value === t.value ? "active" : ""}
          onClick={() => onChange(t.value)}>
          {t.label}
        </button>
      ))}
    </div>
  );
}

/* ---------------- Export / print buttons ---------------- */
export function ExportButtons({ path, params = {}, name = "export", formats = ["xlsx", "csv", "html"] }) {
  const toast = useToast();
  const run = async (fmt) => {
    try {
      if (fmt === "html") await openPrintable(path, { ...params, format: "html" });
      else await download(path, { ...params, format: fmt }, `${name}.${fmt}`);
    } catch (e) {
      toast.error(e);
    }
  };
  return (
    <div className="gap no-print">
      {formats.includes("xlsx") && <Button size="sm" onClick={() => run("xlsx")}>Excel</Button>}
      {formats.includes("csv") && <Button size="sm" onClick={() => run("csv")}>CSV</Button>}
      {formats.includes("html") && <Button size="sm" onClick={() => run("html")}>Print / PDF</Button>}
    </div>
  );
}

export function DateRange({ from, to, onChange }) {
  return (
    <div className="gap">
      <Input type="date" label="From" value={from} onChange={(e) => onChange({ from: e.target.value, to })} />
      <Input type="date" label="To" value={to} onChange={(e) => onChange({ from, to: e.target.value })} />
    </div>
  );
}
