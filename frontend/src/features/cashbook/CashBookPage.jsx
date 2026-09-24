import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, fieldErrors } from "../../api/client";
import { useApi, useInvalidate } from "../../api/hooks";
import DataTable from "../../components/DataTable";
import { Alert, Badge, Button, Card, ConfirmReason, ErrorBox, ExportButtons, Input, Modal, NumInput, PageHead, Select, Stat, Tabs, TextArea, useForm, useToast } from "../../components/ui";
import { useDebounce, usePermissions, useSettings } from "../../hooks";
import { date, dateTime, label, monthStartISO, pkr, todayISO } from "../../utils/format";

function EntryForm({ initial, onClose, onSaved }) {
  const toast = useToast();
  const { data: settings } = useSettings();
  const { data: heads } = useApi("/heads-of-account/", { is_active: true });
  const f = useForm(initial || {
    date: todayISO(), hoa: "", sub_hoa: "", detail: "Cash", debited_to: "Shop", party: "", amount: "", cash_account: "shop_cash",
    book_no: "", page_no: "", pound_weight: "", pasa_weight: "", rate: "", notes: "",
  });
  const tops = (heads || []).filter((h) => !h.parent);
  const subs = (heads || []).filter((h) => h.parent === f.values.hoa);
  const chosen = tops.find((h) => h.id === f.values.hoa);
  const save = async (another) => {
    const body = { ...f.values };
    for (const k of ["sub_hoa", "pound_weight", "pasa_weight", "rate"]) if (body[k] === "") body[k] = null;
    try {
      if (initial?.id) await api.patch(`/cash-book/${initial.id}/`, body);
      else await api.post("/cash-book/", body);
      toast.ok("Entry saved");
      onSaved();
      if (another) f.setValues({ ...f.values, amount: "", party: "", notes: "", sub_hoa: "" });
      else onClose();
    } catch (e) { f.setErrors(fieldErrors(e)); toast.error(e); }
  };
  return (
    <Modal wide title={initial?.id ? "Edit entry" : "New cash book entry"} onClose={onClose} footer={
      <>
        <Button onClick={onClose}>Cancel</Button>
        {!initial?.id && <Button onClick={() => save(true)}>Save & next</Button>}
        <Button variant="primary" onClick={() => save(false)}>Save</Button>
      </>
    }>
      <div className="form-grid">
        <Input type="date" label="Date" {...f.bind("date")} />
        <Select label="Head of account" {...f.bind("hoa")} placeholder="Choose…" className="span-2"
          options={tops.map((h) => ({ value: h.id, label: `${h.type === "I" ? "▲ In" : "▼ Out"} · ${h.name}` }))} />
        <Select label="Sub-head" {...f.bind("sub_hoa")} placeholder={subs.length ? "Choose…" : "—"} options={subs.map((h) => ({ value: h.id, label: h.name }))} />
        <NumInput label={`Amount${chosen ? (chosen.type === "I" ? " (income)" : " (expense)") : ""}`} {...f.bind("amount")} />
        <Select label="Cash account" {...f.bind("cash_account")} options={settings?.cash_accounts || ["shop_cash"]} />
        <Input label="Detail" {...f.bind("detail")} placeholder="Cash / MBI / Salami" />
        <Input label="Debited to" {...f.bind("debited_to")} placeholder="Shop / Home / Refine / name" />
        <Input label="Received from / paid to" className="span-2" {...f.bind("party")} />
        <Input label="Book no." {...f.bind("book_no")} />
        <Input label="Page no." {...f.bind("page_no")} />
        <NumInput label="Pound wt" {...f.bind("pound_weight")} />
        <NumInput label="Pasa wt" {...f.bind("pasa_weight")} />
        <NumInput label="Rate" {...f.bind("rate")} />
        <TextArea label="Notes" className="span-all" {...f.bind("notes")} />
      </div>
      {f.errors.non_field_errors && <Alert kind="error">{f.errors.non_field_errors}</Alert>}
    </Modal>
  );
}

function Entries() {
  const invalidate = useInvalidate();
  const toast = useToast();
  const [search, setSearch] = useState("");
  const [f, setF] = useState({ date_from: todayISO(), date_to: todayISO(), type: "", hoa: "", cash_account: "", is_voided: "false" });
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState(null);
  const [voiding, setVoiding] = useState(null);
  const q = useDebounce(search);
  useEffect(() => setPage(1), [q, f]);
  const params = { search: q, ...f, page };
  const { data, isFetching, error } = useApi("/cash-book/", params);
  const { data: heads } = useApi("/heads-of-account/", { top_level: 1 });
  const { data: settings } = useSettings();
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const saved = () => invalidate("/cash-book", "/dashboard");

  const cols = [
    { key: "date", label: "Date", render: (r) => date(r.date) },
    { key: "type", label: "I/E", render: (r) => <Badge kind={r.type === "I" ? "ok" : "warn"}>{r.type === "I" ? "In" : "Out"}</Badge> },
    { key: "hoa_name", label: "Head", render: (r) => <>{r.hoa_name}{r.sub_hoa_name && <span className="muted"> › {r.sub_hoa_name}</span>}</> },
    { key: "party", label: "Party" },
    { key: "detail", label: "Detail", className: "hide-mobile" },
    { key: "cash_account", label: "Account", className: "hide-mobile" },
    { key: "source_type", label: "Source", className: "hide-mobile", render: (r) => label(r.source_type) },
    { key: "amount", label: "Amount", num: true, render: (r) => pkr(r.amount) },
    { key: "x", label: "", render: (r) => r.is_voided ? <Badge kind="danger">voided</Badge> : r.day_locked ? <span title="Day closed">🔒</span> : r.source_type === "manual" ? (
      <span className="gap" style={{ flexWrap: "nowrap" }}>
        <Button size="sm" variant="ghost" onClick={(e) => { e.stopPropagation(); setEditing(r); }}>Edit</Button>
        <Button size="sm" variant="ghost" onClick={(e) => { e.stopPropagation(); setVoiding(r); }}>Void</Button>
      </span>) : null },
  ];
  const t = data?.totals;

  return (
    <div className="stack">
      <Card>
        <div className="form-grid">
          <Input type="date" label="From" value={f.date_from} onChange={set("date_from")} />
          <Input type="date" label="To" value={f.date_to} onChange={set("date_to")} />
          <Select label="Type" value={f.type} onChange={set("type")} placeholder="All" options={[{ value: "I", label: "Income" }, { value: "E", label: "Expenditure" }]} />
          <Select label="Head" value={f.hoa} onChange={set("hoa")} placeholder="All" options={(heads || []).map((h) => ({ value: h.id, label: `${h.name} (${h.type})` }))} />
          <Select label="Account" value={f.cash_account} onChange={set("cash_account")} placeholder="All" options={settings?.cash_accounts || []} />
          <Select label="Show" value={f.is_voided} onChange={set("is_voided")} placeholder="All" options={[{ value: "false", label: "Active" }, { value: "true", label: "Voided" }]} />
          <Input label="Search" className="span-2" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Party, detail, head…" />
        </div>
      </Card>
      <div className="gap">
        {t && <><span className="badge ok">In {pkr(t.income)}</span><span className="badge warn">Out {pkr(t.expenditure)}</span><span className="badge accent">Net {pkr(t.net)}</span></>}
        <div className="spacer" />
        <ExportButtons path="/cash-book/" params={{ search: q, ...f }} name="cash-book" />
        <Button variant="primary" onClick={() => setEditing({})}>New entry</Button>
      </div>
      <ErrorBox error={error} />
      <Card bodyClass=""><DataTable columns={cols} data={data} loading={isFetching} page={page} setPage={setPage} rowClass={(r) => (r.is_voided ? "voided" : "")} /></Card>
      {editing && <EntryForm initial={editing.id ? { ...editing, sub_hoa: editing.sub_hoa || "" } : null} onClose={() => setEditing(null)} onSaved={saved} />}
      {voiding && (
        <ConfirmReason title="Void entry?" prompt={`${voiding.hoa_name} · Rs ${pkr(voiding.amount)}`} confirmLabel="Void"
          onClose={() => setVoiding(null)}
          onConfirm={async (reason) => {
            try { await api.post(`/cash-book/${voiding.id}/void/`, { reason }); setVoiding(null); saved(); toast.ok("Voided"); } catch (e) { toast.error(e); }
          }} />
      )}
    </div>
  );
}

function DayClose() {
  const perms = usePermissions();
  const toast = useToast();
  const invalidate = useInvalidate();
  const [day, setDay] = useState(todayISO());
  const [counted, setCounted] = useState("");
  const [notes, setNotes] = useState("");
  const { data: s, refetch } = useApi("/cash-book/day-summary/", { date: day });
  const { data: history } = useApi("/cash-book/day-closes/");
  const act = async (path, body, msg) => {
    try { await api.post(path, body); toast.ok(msg); refetch(); invalidate("/cash-book", "/dashboard"); } catch (e) { toast.error(e); }
  };
  const diff = counted !== "" && s ? Number(counted) - Number(s.breakdown?.shop_cash?.closing || 0) : null;
  return (
    <div className="stack">
      <div className="gap"><Input type="date" label="Day" value={day} onChange={(e) => setDay(e.target.value)} />{s?.is_locked && <Badge kind="info">Closed</Badge>}</div>
      {s && (
        <>
          <div className="grid grid-4">
            <Stat label="Opening" value={pkr(s.opening_balance)} />
            <Stat label="Income" value={pkr(s.total_income)} />
            <Stat label="Expenditure" value={pkr(s.total_expenditure)} />
            <Stat label="Closing" value={pkr(s.closing_balance)} hint={`${s.entry_count} entries`} />
          </div>
          <Card title="By account" bodyClass="table-wrap">
            <table className="table">
              <thead><tr><th>Account</th><th className="num">Opening</th><th className="num">In</th><th className="num">Out</th><th className="num">Closing</th></tr></thead>
              <tbody>{Object.entries(s.breakdown).map(([acc, b]) => (
                <tr key={acc}><td>{acc}</td><td className="num">{pkr(b.opening)}</td><td className="num">{pkr(b.income)}</td><td className="num">{pkr(b.expenditure)}</td><td className="num strong">{pkr(b.closing)}</td></tr>
              ))}</tbody>
            </table>
          </Card>
          {!s.is_locked && perms.day_close && (
            <Card title="Close the day">
              <div className="form-grid">
                <NumInput label="Cash counted in drawer (optional)" value={counted} onChange={(e) => setCounted(e.target.value)} />
                <Input label="Notes" className="span-2" value={notes} onChange={(e) => setNotes(e.target.value)} />
              </div>
              {diff !== null && <p className={diff === 0 ? "" : "strong"} style={{ color: diff === 0 ? "var(--ok)" : "var(--danger)" }}>Difference vs shop_cash: {pkr(diff)}</p>}
              <Button variant="primary" onClick={() => act("/cash-book/day-close/", { date: day, counted_cash: counted || null, notes }, "Day closed")}>Close {date(day)}</Button>
              <p className="small muted">Closing locks this day's cash-book entries. Only the owner can reopen.</p>
            </Card>
          )}
          {s.is_locked && perms.day_reopen && (
            <Button variant="danger" onClick={() => act("/cash-book/day-reopen/", { date: day, reason: "Reopened from cash book" }, "Day reopened")}>Reopen {date(day)}</Button>
          )}
        </>
      )}
      <Card title="Recent day closes" bodyClass="table-wrap">
        <table className="table">
          <thead><tr><th>Date</th><th className="num">Opening</th><th className="num">In</th><th className="num">Out</th><th className="num">Closing</th><th className="num">Counted</th><th>Closed by</th><th>Status</th></tr></thead>
          <tbody>{(history || []).map((h) => (
            <tr key={h.date} className="clickable" onClick={() => setDay(h.date)}>
              <td>{date(h.date)}</td><td className="num">{pkr(h.opening_balance)}</td><td className="num">{pkr(h.total_income)}</td><td className="num">{pkr(h.total_expenditure)}</td>
              <td className="num strong">{pkr(h.closing_balance)}</td><td className="num">{h.counted_cash ? pkr(h.counted_cash) : "—"}</td>
              <td>{h.locked_by_name} <span className="muted small">{dateTime(h.locked_at)}</span></td>
              <td>{h.is_locked ? <Badge kind="info">closed</Badge> : <Badge kind="warn">reopened</Badge>}</td>
            </tr>
          ))}</tbody>
        </table>
      </Card>
    </div>
  );
}

function SavedViews() {
  const { data: views } = useApi("/cash-book/saved-views/");
  const [group, setGroup] = useState("shop_expenses");
  const [range, setRange] = useState({ date_from: monthStartISO(), date_to: todayISO() });
  const [page, setPage] = useState(1);
  const { data, isFetching, error } = useApi(`/cash-book/views/${group}/`, { ...range, page });
  const cols = [
    { key: "date", label: "Date", render: (r) => date(r.date) },
    { key: "hoa_name", label: "Head", render: (r) => <>{r.hoa_name}{r.sub_hoa_name && <span className="muted"> › {r.sub_hoa_name}</span>}</> },
    { key: "party", label: "Party" },
    { key: "debited_to", label: "Debited to", className: "hide-mobile" },
    { key: "amount", label: "Amount", num: true, render: (r) => <span style={{ color: r.type === "I" ? "var(--ok)" : undefined }}>{pkr(r.amount)}</span> },
  ];
  return (
    <div className="stack">
      <div className="form-grid">
        <Select label="View" value={group} onChange={(e) => { setGroup(e.target.value); setPage(1); }} options={(views || []).map((v) => ({ value: v.key, label: v.title }))} />
        <Input type="date" label="From" value={range.date_from} onChange={(e) => setRange({ ...range, date_from: e.target.value })} />
        <Input type="date" label="To" value={range.date_to} onChange={(e) => setRange({ ...range, date_to: e.target.value })} />
      </div>
      <ErrorBox error={error} />
      {data && (
        <div className="grid grid-2">
          <Card title={`${data.title} — by head`} bodyClass="" actions={<ExportButtons path={`/cash-book/views/${group}/`} params={range} name={group} />}>
            <table className="table"><tbody>
              {data.by_head.map((b, i) => (
                <tr key={i}><td>{b.hoa__name}{b.sub_hoa__name && <span className="muted"> › {b.sub_hoa__name}</span>}</td><td>{b.type}</td><td className="num">{pkr(b.total)}</td></tr>
              ))}
              <tr><td className="strong">Net</td><td /><td className="num strong">{pkr(data.totals.net)}</td></tr>
            </tbody></table>
          </Card>
          <Card bodyClass=""><DataTable columns={cols} data={data} loading={isFetching} page={page} setPage={setPage} /></Card>
        </div>
      )}
    </div>
  );
}

export default function CashBookPage() {
  const [sp, setSp] = useSearchParams();
  const tab = sp.get("tab") || "entries";
  return (
    <div className="stack">
      <PageHead title="Cash book" subtitle="Day book of all income and expenditure. Sales, advances and payments post here automatically.">
        <Link className="btn" to="/heads-of-account">Heads of account</Link>
      </PageHead>
      <Tabs value={tab} onChange={(t) => setSp({ tab: t })} tabs={[
        { value: "entries", label: "Entries" }, { value: "day", label: "Day close" }, { value: "views", label: "Saved views" },
      ]} />
      {tab === "entries" && <Entries />}
      {tab === "day" && <DayClose />}
      {tab === "views" && <SavedViews />}
    </div>
  );
}
