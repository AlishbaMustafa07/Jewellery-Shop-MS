import { useState } from "react";
import { useApi } from "../api/hooks";
import { useDebounce } from "../hooks";
import { pkr } from "../utils/format";
import { Field } from "./ui";

/** Type-ahead search over a DRF list endpoint. */
export function SearchPicker({ label, path, params = {}, value, onChange, renderItem, placeholder, error, autoFocus }) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [hl, setHl] = useState(0);
  const search = useDebounce(q, 200);
  const { data } = useApi(open ? path : null, { search, page_size: 12, ...params });
  const items = data?.results || [];

  const choose = (item) => {
    onChange(item);
    setQ("");
    setOpen(false);
  };

  if (value) {
    return (
      <Field label={label} error={error}>
        <div className="gap" style={{ border: "1px solid var(--border)", borderRadius: 7, padding: "5px 9px", minHeight: 34 }}>
          <span className="strong">{renderItem(value)}</span>
          <div className="spacer" />
          <button type="button" className="btn ghost sm" onClick={() => onChange(null)} aria-label="Clear">✕</button>
        </div>
      </Field>
    );
  }
  return (
    <Field label={label} error={error}>
      <div className="rel">
        <input value={q} placeholder={placeholder} autoFocus={autoFocus}
          onChange={(e) => { setQ(e.target.value); setOpen(true); setHl(0); }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setHl((h) => Math.min(h + 1, items.length - 1)); }
            if (e.key === "ArrowUp") { e.preventDefault(); setHl((h) => Math.max(h - 1, 0)); }
            if (e.key === "Enter" && items[hl]) { e.preventDefault(); choose(items[hl]); }
          }} />
        {open && items.length > 0 && (
          <div className="suggest">
            {items.map((it, i) => (
              <button type="button" key={it.id} className={i === hl ? "hl" : ""} onMouseDown={() => choose(it)}>
                {renderItem(it)}
              </button>
            ))}
          </div>
        )}
      </div>
    </Field>
  );
}

export function CustomerPicker(props) {
  return (
    <SearchPicker path="/customers/" placeholder="Search name or phone…" {...props}
      renderItem={(c) => (
        <span>
          {c.name} <span className="muted">{c.phone}</span>
          {Number(c.balance) !== 0 && <span className="muted"> · bal {pkr(c.balance)}</span>}
        </span>
      )} />
  );
}

export function SupplierPicker(props) {
  return (
    <SearchPicker path="/suppliers/" placeholder="Search supplier…" {...props}
      renderItem={(s) => <span>{s.name} <span className="muted">({s.type})</span></span>} />
  );
}
