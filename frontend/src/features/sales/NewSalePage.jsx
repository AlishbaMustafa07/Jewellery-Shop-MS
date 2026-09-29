import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, errorMessage, openPrintable } from "../../api/client";
import { useApi, useInvalidate } from "../../api/hooks";
import { CustomerPicker } from "../../components/Pickers";
import { Alert, Button, Card, Field, Input, NumInput, PageHead, useToast } from "../../components/ui";
import { useDebounce, useGoldRate, useLocalState, usePermissions, useRole, useSettings } from "../../hooks";
import { pasa, pkr, toNum, wt } from "../../utils/format";

const MAKING_MODES = [
  { value: "fixed", label: "Rs (fixed)" },
  { value: "per_gram", label: "Rs / gram" },
  { value: "per_tola", label: "Rs / tola" },
  { value: "percent", label: "% of gold" },
];
const PAY_METHODS = ["cash", "bank", "card", "advance"];
let uid = 0;
const newKey = () => `k${++uid}`;

function blankSale() {
  return {
    lines: [], customer: null, walkInName: "", walkInPhone: "", newCustomer: false, discount: "", saleRate: "",
    oldGold: [], payments: [{ key: newKey(), method: "cash", amount: "" }], notes: "", legacyBook: "", legacyPage: "",
  };
}

function ItemSearch({ onAdd, inputRef }) {
  const [q, setQ] = useState("");
  const [hl, setHl] = useState(0);
  const search = useDebounce(q, 150);
  const { data } = useApi(search.length >= 2 ? "/stock/" : null, { search, status: "in_stock", page_size: 10 });
  const items = data?.results || [];
  const add = (it) => {
    onAdd(it);
    setQ("");
    setHl(0);
  };
  const enter = async () => {
    const code = q.trim().toUpperCase();
    if (!code) return;
    const exact = items.find((i) => i.code === code);
    if (exact) return add(exact);
    if (items[hl] && search === q) return add(items[hl]);
    // Scanner is faster than the debounce — look the code up directly.
    const { data: r } = await api.get("/stock/", { params: { search: code, page_size: 5 } });
    const hit = r.results.find((i) => i.code === code) || (r.results.length === 1 ? r.results[0] : null);
    if (hit) add(hit);
    else onAdd(null, `No item found for "${code}".`);
  };
  return (
    <div className="rel">
      <input ref={inputRef} className="scan" value={q} placeholder="Scan tag or type code / name, then Enter"
        onChange={(e) => { setQ(e.target.value); setHl(0); }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setHl((h) => Math.min(h + 1, items.length - 1)); }
          if (e.key === "ArrowUp") { e.preventDefault(); setHl((h) => Math.max(h - 1, 0)); }
          if (e.key === "Enter") { e.preventDefault(); enter(); }
        }} autoFocus />
      {q && items.length > 0 && (
        <div className="suggest">
          {items.map((it, i) => (
            <button type="button" key={it.id} className={i === hl ? "hl" : ""} onMouseDown={() => add(it)}>
              <span className="mono strong">{it.code}</span>
              <span>{it.category}</span>
              <span className="muted">{wt(it.gross_weight)} g · {it.ratti_kaat} ratti</span>
              <span className="spacer" />
              {it.value_at_today && <span className="muted">≈ {pkr(it.value_at_today)}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function NewSalePage() {
  const toast = useToast();
  const invalidate = useInvalidate();
  const perms = usePermissions();
  const role = useRole();
  const { rate, isToday } = useGoldRate();
  const { data: settings } = useSettings();
  const [sp, setSp] = useSearchParams();
  const [sale, setSale] = useState(blankSale);
  const [preview, setPreview] = useState(null);
  const [previewError, setPreviewError] = useState("");
  const [saving, setSaving] = useState(false);
  const [last, setLast] = useState(null);
  const [receiptSize, setReceiptSize] = useLocalState("alnoor.receiptSize", "80mm");
  const searchRef = useRef(null);
  const canOverride = role === "owner" || role === "manager";

  const upd = (patch) => setSale((s) => ({ ...s, ...patch }));
  const updLine = (key, patch) => setSale((s) => ({ ...s, lines: s.lines.map((l) => (l.key === key ? { ...l, ...patch } : l)) }));
  const updList = (list, key, patch) => setSale((s) => ({ ...s, [list]: s[list].map((l) => (l.key === key ? { ...l, ...patch } : l)) }));

  const addItem = (item, err) => {
    if (!item) return toast.error(err);
    if (item.status !== "in_stock") return toast.error(`${item.code} is not in stock (${item.status}).`);
    setSale((s) => {
      if (s.lines.some((l) => l.item?.id === item.id)) {
        toast.error(`${item.code} is already on this sale.`);
        return s;
      }
      return { ...s, lines: [...s.lines, { key: newKey(), item, makingMode: "fixed", making: "", stone: "", metalValue: "" }] };
    });
  };
  const addMisc = () =>
    setSale((s) => ({ ...s, lines: [...s.lines, { key: newKey(), item: null, description: "", weight: "", ratti: "", metalValue: "", makingMode: "fixed", making: "", stone: "" }] }));

  // Preload ?item=CODE (from the stock page "Sell" button)
  useEffect(() => {
    const code = sp.get("item");
    if (!code) return;
    api.get("/stock/", { params: { search: code } }).then(({ data }) => {
      const it = data.results.find((i) => i.code === code);
      if (it) addItem(it);
      setSp({}, { replace: true });
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const payload = useMemo(() => {
    const lines = sale.lines.map((l) => {
      const base = {
        making_mode: l.makingMode,
        ...(l.makingMode === "fixed" ? { making_charges: l.making || "0" } : { making_rate: l.making || "0" }),
        stone_value: l.stone || "0",
      };
      if (l.item) {
        return { ...base, stock_item: l.item.id, ...(l.item.metal !== "gold" ? { gold_value: l.metalValue || "0" } : {}) };
      }
      return {
        ...base, description: l.description || "Misc item", weight: l.weight || null, ratti_kaat: l.ratti || null,
        ...(l.metalValue !== "" ? { gold_value: l.metalValue } : {}),
      };
    });
    const body = {
      lines,
      discount: sale.discount || "0",
      old_gold: sale.oldGold.filter((o) => toNum(o.weight) > 0).map((o) => ({
        description: o.description, weight: o.weight, ratti_kaat: o.ratti || "0", ...(o.rate ? { rate: o.rate } : {}), deduction: o.deduction || "0",
      })),
      payments: sale.payments.filter((p) => toNum(p.amount) > 0).map((p) => ({ method: p.method, amount: p.amount, reference: p.reference || "" })),
      notes: sale.notes,
      legacy_book: sale.legacyBook,
      legacy_page: sale.legacyPage,
    };
    if (sale.saleRate && canOverride) body.sale_rate = sale.saleRate;
    if (sale.customer) body.customer = sale.customer.id;
    else if (sale.newCustomer && sale.walkInName) body.new_customer = { name: sale.walkInName, phone: sale.walkInPhone };
    else { body.customer_name = sale.walkInName; body.customer_phone = sale.walkInPhone; }
    return body;
  }, [sale, canOverride]);

  const debounced = useDebounce(payload, 250);
  useEffect(() => {
    if (!debounced.lines.length) { setPreview(null); setPreviewError(""); return; }
    let cancelled = false;
    api.post("/sale-preview/", debounced)
      .then(({ data }) => { if (!cancelled) { setPreview(data); setPreviewError(""); } })
      .catch((e) => { if (!cancelled) setPreviewError(errorMessage(e)); });
    return () => { cancelled = true; };
  }, [debounced]);

  const balance = preview ? toNum(preview.balance) : 0;
  const payRemaining = (method = "cash") => {
    if (!preview) return;
    const others = sale.payments.slice(1).reduce((a, p) => a + toNum(p.amount), 0);
    const due = toNum(preview.net_amount) - toNum(preview.old_gold_credit) - others;
    const [first, ...rest] = sale.payments;
    upd({ payments: [{ ...first, method, amount: String(Math.max(0, Math.round(due))) }, ...rest] });
  };

  const save = async () => {
    setSaving(true);
    try {
      const { data } = await api.post("/invoices/", payload);
      toast.ok(`Invoice ${data.number} saved`);
      setLast(data);
      setSale(blankSale());
      setPreview(null);
      invalidate("/stock", "/invoices", "/dashboard", "/customers", "/cash-book", "/advances");
      openPrintable(`/invoices/${data.id}/receipt/`, { size: receiptSize });
      searchRef.current?.focus();
    } catch (e) {
      toast.error(e);
    } finally {
      setSaving(false);
    }
  };

  const lineCalc = (i) => preview?.lines?.[i];
  const walkIn = !sale.customer;

  return (
    <div className="stack">
      <PageHead title="New sale" subtitle="Scan or search items · adjust making/discount · take payment · print">
        {last && (
          <>
            <Link className="btn" to={`/invoices/${last.id}`}>Last: {last.number}</Link>
            <Button onClick={() => openPrintable(`/invoices/${last.id}/receipt/`, { size: receiptSize })}>Reprint</Button>
          </>
        )}
      </PageHead>
      {!rate && <Alert kind="error">No gold rate has been entered. <Link to="/rates">Set today's rate</Link> before selling.</Alert>}
      {rate && !isToday && <Alert kind="warn">Using the last rate ({pkr(rate.sell_rate_per_tola)}) — today's rate is not set. <Link to="/rates">Set it</Link></Alert>}

      <div className="pos">
        <div className="stack">
          <Card>
            <ItemSearch onAdd={addItem} inputRef={searchRef} />
            <div className="gap" style={{ marginTop: 8 }}>
              <Button size="sm" onClick={addMisc}>+ Misc / non-stock line</Button>
              <span className="muted small">Gold is priced at {settings?.sale_gold_basis === "weight" ? "gold weight" : "pasa"} × sell rate ÷ 11.664</span>
            </div>
          </Card>

          <Card title={`Items (${sale.lines.length})`} bodyClass="table-wrap">
            <table className="table">
              <thead><tr>
                <th>Item</th><th className="num">Wt / pasa</th><th className="num">Metal value</th>
                <th>Making</th><th className="num">Stone</th><th className="num">Total</th><th />
              </tr></thead>
              <tbody>
                {sale.lines.map((l, i) => {
                  const c = lineCalc(i);
                  const isGold = l.item?.metal === "gold";
                  return (
                    <tr key={l.key}>
                      <td style={{ minWidth: 120 }}>
                        {l.item ? (
                          <><span className="mono strong">{l.item.code}</span><div className="small muted">{l.item.category} · {l.item.ratti_kaat} ratti{l.item.metal !== "gold" ? ` · ${l.item.metal}` : ""}</div></>
                        ) : (
                          <div className="stack" style={{ gap: 4 }}>
                            <input placeholder="Description" value={l.description} onChange={(e) => updLine(l.key, { description: e.target.value })} />
                            <div className="gap" style={{ flexWrap: "nowrap" }}>
                              <input className="num" placeholder="Wt g" value={l.weight} onChange={(e) => updLine(l.key, { weight: e.target.value })} />
                              <input className="num" placeholder="Ratti" value={l.ratti} onChange={(e) => updLine(l.key, { ratti: e.target.value })} />
                            </div>
                          </div>
                        )}
                      </td>
                      <td className="num">{c ? <>{wt(c.weight)}<div className="small muted">{pasa(c.pasa)}</div></> : "—"}</td>
                      <td className="num" style={{ minWidth: 110 }}>
                        {isGold ? pkr(c?.gold_value) : (
                          <input className="num" placeholder={l.item ? "Price" : "Auto / Rs"} value={l.metalValue}
                            onChange={(e) => updLine(l.key, { metalValue: e.target.value })} />
                        )}
                      </td>
                      <td style={{ minWidth: 176 }}>
                        <div className="gap" style={{ flexWrap: "nowrap" }}>
                          <select value={l.makingMode} onChange={(e) => updLine(l.key, { makingMode: e.target.value })} style={{ width: 96 }}>
                            {MAKING_MODES.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
                          </select>
                          <input className="num" style={{ width: 76 }} value={l.making} placeholder="0" onChange={(e) => updLine(l.key, { making: e.target.value })} />
                        </div>
                        {l.makingMode !== "fixed" && c && <div className="small muted right">= {pkr(c.making_charges)}</div>}
                      </td>
                      <td className="num"><input className="num" style={{ width: 76 }} value={l.stone} placeholder="0" onChange={(e) => updLine(l.key, { stone: e.target.value })} /></td>
                      <td className="num strong">{pkr(c?.line_total)}
                        {perms.view_profit && c?.profit !== undefined && <div className="small muted">P {pkr(c.profit)}</div>}
                      </td>
                      <td><Button size="sm" variant="ghost" aria-label="Remove" onClick={() => upd({ lines: sale.lines.filter((x) => x.key !== l.key) })}>✕</Button></td>
                    </tr>
                  );
                })}
                {!sale.lines.length && <tr><td colSpan={7} className="empty">Scan a tag or search above to add items.</td></tr>}
              </tbody>
            </table>
          </Card>

          <Card title="Customer">
            <div className="form-grid">
              <div className="span-2">
                <CustomerPicker label="Existing customer" value={sale.customer} onChange={(c) => upd({ customer: c })} />
              </div>
              {walkIn && (
                <>
                  <Input label={sale.newCustomer ? "New customer name" : "Walk-in name (optional)"} value={sale.walkInName} onChange={(e) => upd({ walkInName: e.target.value })} />
                  <Input label="Phone" value={sale.walkInPhone} onChange={(e) => upd({ walkInPhone: e.target.value })} />
                  <label className="check span-2"><input type="checkbox" checked={sale.newCustomer} onChange={(e) => upd({ newCustomer: e.target.checked })} /> Save as a new customer (needed to leave a balance)</label>
                </>
              )}
              {sale.customer && <div className="span-2 small muted">Balance {pkr(sale.customer.balance)} (negative = advance/credit available)</div>}
            </div>
          </Card>

          <Card title="Old gold exchange" actions={<Button size="sm" onClick={() => upd({ oldGold: [...sale.oldGold, { key: newKey(), description: "", weight: "", ratti: "", rate: "", deduction: "" }] })}>+ Add old gold</Button>}>
            {!sale.oldGold.length && <div className="muted small">Customer is not giving old gold.</div>}
            {sale.oldGold.map((o, i) => (
              <div key={o.key} className="form-grid" style={{ marginBottom: 8, alignItems: "end" }}>
                <Input label="Description" value={o.description} onChange={(e) => updList("oldGold", o.key, { description: e.target.value })} />
                <NumInput label="Weight (g)" value={o.weight} onChange={(e) => updList("oldGold", o.key, { weight: e.target.value })} />
                <NumInput label="Ratti kaat" value={o.ratti} onChange={(e) => updList("oldGold", o.key, { ratti: e.target.value })} />
                <NumInput label="Rate / tola" value={o.rate} placeholder={rate?.buy_rate_per_tola} onChange={(e) => updList("oldGold", o.key, { rate: e.target.value })} />
                <NumInput label="Deduction Rs" value={o.deduction} onChange={(e) => updList("oldGold", o.key, { deduction: e.target.value })} />
                <div className="gap">
                  <span className="strong">{preview?.old_gold?.[i] ? `Rs ${pkr(preview.old_gold[i].value)}` : ""}</span>
                  <Button size="sm" variant="ghost" onClick={() => upd({ oldGold: sale.oldGold.filter((x) => x.key !== o.key) })}>✕</Button>
                </div>
              </div>
            ))}
          </Card>

          <Card title="More">
            <div className="form-grid">
              {canOverride && <NumInput label="Override sell rate / tola" value={sale.saleRate} placeholder={rate?.sell_rate_per_tola} onChange={(e) => upd({ saleRate: e.target.value })} />}
              <Input label="Legacy book" value={sale.legacyBook} onChange={(e) => upd({ legacyBook: e.target.value })} />
              <Input label="Legacy page" value={sale.legacyPage} onChange={(e) => upd({ legacyPage: e.target.value })} />
              <Input label="Notes" className="span-2" value={sale.notes} onChange={(e) => upd({ notes: e.target.value })} />
            </div>
          </Card>
        </div>

        <div className="summary stack">
          <Card title="Summary">
            <div className="summary-row"><span>Sell rate</span><span>{pkr(preview?.sale_rate || rate?.sell_rate_per_tola)}</span></div>
            <div className="summary-row"><span>Subtotal</span><span>{pkr(preview?.subtotal || 0)}</span></div>
            <div className="summary-row" style={{ alignItems: "center" }}>
              <span>Discount{perms.discount_limit ? <span className="small muted"> (max {pkr(perms.discount_limit)})</span> : ""}</span>
              <input className="num" style={{ width: 110 }} value={sale.discount} placeholder="0" onChange={(e) => upd({ discount: e.target.value })} />
            </div>
            <div className="summary-row total"><span>Net</span><span>Rs {pkr(preview?.net_amount || 0)}</span></div>
            {preview && toNum(preview.old_gold_credit) > 0 && <div className="summary-row"><span>Old gold credit</span><span>− {pkr(preview.old_gold_credit)}</span></div>}
            {perms.view_profit && preview?.profit !== undefined && <div className="summary-row small muted"><span>Profit (approx.)</span><span>{pkr(preview.profit)}</span></div>}
          </Card>

          <Card title="Payment" actions={<Button size="sm" onClick={() => upd({ payments: [...sale.payments, { key: newKey(), method: "bank", amount: "" }] })}>+ Split</Button>}>
            {sale.payments.map((p, i) => (
              <div key={p.key} className="gap" style={{ marginBottom: 8, flexWrap: "nowrap" }}>
                <select value={p.method} style={{ width: 110 }} onChange={(e) => updList("payments", p.key, { method: e.target.value })}>
                  {PAY_METHODS.filter((m) => m !== "advance" || sale.customer).map((m) => <option key={m} value={m}>{m === "advance" ? "From advance" : m[0].toUpperCase() + m.slice(1)}</option>)}
                </select>
                <input className="num" value={p.amount} placeholder="0" onChange={(e) => updList("payments", p.key, { amount: e.target.value })} />
                {i > 0 && <Button size="sm" variant="ghost" onClick={() => upd({ payments: sale.payments.filter((x) => x.key !== p.key) })}>✕</Button>}
              </div>
            ))}
            <div className="gap">
              <Button size="sm" onClick={() => payRemaining("cash")} disabled={!preview}>Full in cash</Button>
              <Button size="sm" onClick={() => payRemaining("card")} disabled={!preview}>Full by card</Button>
            </div>
            <div className={`summary-row balance`} style={{ marginTop: 10 }}>
              <span>{balance < 0 ? "Change to give" : "Balance due"}</span>
              <span style={{ color: balance > 0 ? "var(--warn)" : balance < 0 ? "var(--danger)" : "var(--ok)" }}>Rs {pkr(Math.abs(balance))}</span>
            </div>
            {balance < 0 && <div className="small muted">Record only what is kept — reduce the payment by the change.</div>}
            {balance > 0 && walkIn && !sale.newCustomer && <div className="small muted">Walk-in sales must be paid in full, or save the customer.</div>}
          </Card>

          {previewError && <Alert kind="error">{previewError}</Alert>}
          <Field label="Receipt">
            <select value={receiptSize} onChange={(e) => setReceiptSize(e.target.value)}>
              <option value="80mm">80 mm thermal</option>
              <option value="a4">A4</option>
            </select>
          </Field>
          <Button variant="primary" size="lg" disabled={!sale.lines.length || saving || !!previewError || balance < 0} onClick={save}>
            {saving ? "Saving…" : "Save & print receipt"}
          </Button>
          <Button variant="ghost" onClick={() => { setSale(blankSale()); setPreview(null); }}>Clear sale</Button>
        </div>
      </div>
    </div>
  );
}

