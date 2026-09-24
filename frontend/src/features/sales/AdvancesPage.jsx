import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import { useApi, useInvalidate } from "../../api/hooks";
import DataTable from "../../components/DataTable";
import { CustomerPicker } from "../../components/Pickers";
import { Button, Card, ConfirmReason, ErrorBox, Input, NumInput, PageHead, Select, useToast } from "../../components/ui";
import { usePermissions } from "../../hooks";
import { date, label, pkr, todayISO } from "../../utils/format";

export default function AdvancesPage() {
  const toast = useToast();
  const perms = usePermissions();
  const invalidate = useInvalidate();
  const [page, setPage] = useState(1);
  const [customer, setCustomer] = useState(null);
  const [form, setForm] = useState({ method: "cash", amount: "", reference: "", notes: "", date: todayISO() });
  const [busy, setBusy] = useState(false);
  const [voiding, setVoiding] = useState(null);
  const { data, isFetching, error } = useApi("/advances/", { page });

  const save = async () => {
    setBusy(true);
    try {
      await api.post("/advances/", { ...form, customer: customer?.id });
      toast.ok("Advance recorded");
      setForm({ ...form, amount: "", reference: "", notes: "" });
      setCustomer(null);
      invalidate("/advances", "/customers", "/cash-book", "/dashboard");
    } catch (e) { toast.error(e); } finally { setBusy(false); }
  };

  const columns = [
    { key: "date", label: "Date", render: (r) => date(r.date) },
    { key: "customer_name", label: "Customer", render: (r) => <Link to={`/customers/${r.customer}`}>{r.customer_name}</Link> },
    { key: "method", label: "Method", render: (r) => label(r.method) },
    { key: "amount", label: "Amount", num: true, render: (r) => pkr(r.amount) },
    { key: "notes", label: "Notes", className: "hide-mobile" },
    { key: "created_by_name", label: "By", className: "hide-mobile" },
    { key: "x", label: "", render: (r) => r.is_voided ? <span className="badge danger">voided</span> : perms.void_invoice ? <Button size="sm" variant="ghost" onClick={(e) => { e.stopPropagation(); setVoiding(r); }}>Void</Button> : null },
  ];

  return (
    <div className="stack">
      <PageHead title="Advances" subtitle="Money received against a future sale. Adjust it at the counter with the 'From advance' payment method." />
      <Card title="Receive advance">
        <div className="form-grid">
          <div className="span-2"><CustomerPicker label="Customer" value={customer} onChange={setCustomer} /></div>
          <Select label="Method" value={form.method} onChange={(e) => setForm({ ...form, method: e.target.value })} options={["cash", "bank", "card"]} />
          <NumInput label="Amount" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
          <Input type="date" label="Date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
          <Input label="Notes (item ordered…)" className="span-2" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
        </div>
        <div className="gap" style={{ marginTop: 12 }}>
          <Button variant="primary" disabled={!customer || !(Number(form.amount) > 0) || busy} onClick={save}>Save advance</Button>
          <span className="muted small">New customer? <Link to="/customers?new=1">Add them first</Link>.</span>
        </div>
      </Card>
      <ErrorBox error={error} />
      <Card bodyClass=""><DataTable columns={columns} data={data} loading={isFetching} page={page} setPage={setPage} rowClass={(r) => (r.is_voided ? "voided" : "")} /></Card>
      {voiding && (
        <ConfirmReason title="Void advance?" prompt={`Rs ${pkr(voiding.amount)} from ${voiding.customer_name} will be reversed in the cash book.`}
          confirmLabel="Void advance" onClose={() => setVoiding(null)}
          onConfirm={async (reason) => {
            try {
              await api.post(`/payments/${voiding.id}/void/`, { reason });
              toast.ok("Advance voided");
              setVoiding(null);
              invalidate("/advances", "/customers", "/cash-book");
            } catch (e) { toast.error(e); }
          }} />
      )}
    </div>
  );
}
