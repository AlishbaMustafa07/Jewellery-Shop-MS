import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { useApi, useInvalidate } from "../../api/hooks";
import DataTable from "../../components/DataTable";
import { Badge, Button, Card, DateRange, ErrorBox, ExportButtons, Loading, PageHead, Stat, Tabs, useToast } from "../../components/ui";
import { date, label, pkr } from "../../utils/format";
import { PaymentModal } from "../sales/InvoiceDetailPage";
import { CustomerForm } from "./CustomersPage";

export function Statement({ path, name }) {
  const [range, setRange] = useState({ from: "", to: "" });
  const params = { date_from: range.from, date_to: range.to };
  const { data, isFetching } = useApi(path, params);
  const cols = [
    { key: "date", label: "Date", render: (r) => date(r.date) },
    { key: "type", label: "Type" },
    { key: "ref", label: "Ref", className: "mono" },
    { key: "description", label: "Description", className: "hide-mobile" },
    { key: "debit", label: "Debit", num: true, render: (r) => (Number(r.debit) ? pkr(r.debit) : "") },
    { key: "credit", label: "Credit", num: true, render: (r) => (Number(r.credit) ? pkr(r.credit) : "") },
    { key: "balance", label: "Balance", num: true, render: (r) => pkr(r.balance) },
  ];
  return (
    <Card bodyClass="" title={<DateRange from={range.from} to={range.to} onChange={setRange} />}
      actions={<ExportButtons path={path} params={params} name={`statement-${name}`} formats={["xlsx", "html"]} />}>
      {data && <div className="card-body small">Opening balance <b>{pkr(data.opening_balance)}</b> · Closing <b>{pkr(data.closing_balance)}</b></div>}
      <DataTable columns={cols} data={data?.rows || []} loading={isFetching}
        footer={data ? { description: "Totals", debit: pkr(data.total_debit), credit: pkr(data.total_credit), balance: pkr(data.closing_balance) } : null} />
    </Card>
  );
}

export default function CustomerDetailPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const toast = useToast();
  const invalidate = useInvalidate();
  const [tab, setTab] = useState("invoices");
  const [editing, setEditing] = useState(false);
  const [paying, setPaying] = useState(false);
  const { data: c, isLoading, error, refetch } = useApi(`/customers/${id}/`);
  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;

  const invCols = [
    { key: "number", label: "Invoice", render: (r) => <span className="mono">{r.number}</span> },
    { key: "date", label: "Date", render: (r) => date(r.date) },
    { key: "net_amount", label: "Net", num: true, render: (r) => pkr(r.net_amount) },
    { key: "balance", label: "Balance", num: true, render: (r) => pkr(r.balance) },
    { key: "status", label: "Status", render: (r) => <Badge>{r.status}</Badge> },
  ];
  const payCols = [
    { key: "date", label: "Date", render: (r) => date(r.date) },
    { key: "kind", label: "Kind", render: (r) => label(r.kind) },
    { key: "method", label: "Method", render: (r) => label(r.method) },
    { key: "invoice_number", label: "Invoice", render: (r) => r.invoice_number || "—" },
    { key: "amount", label: "Amount", num: true, render: (r) => pkr(r.amount) },
  ];

  return (
    <div className="stack">
      <PageHead title={c.name} subtitle={[c.phone, c.address].filter(Boolean).join(" · ")}>
        <Button onClick={() => setEditing(true)}>Edit</Button>
        <Button variant="primary" onClick={() => setPaying(true)}>Receive payment</Button>
        <Link className="btn" to="/sales/new">New sale</Link>
      </PageHead>
      <div className="grid grid-4">
        <Stat label="Balance" value={`Rs ${pkr(c.balance)}`} hint={Number(c.balance) > 0 ? "Customer owes shop" : Number(c.balance) < 0 ? "Shop owes customer / advance" : "Settled"} />
        <Stat label="Advance available" value={`Rs ${pkr(c.advance_credit)}`} />
        <Stat label="Invoices" value={c.invoices.length} />
        <Stat label="Opening balance" value={`Rs ${pkr(c.opening_balance)}`} hint="From old books" />
      </div>
      {c.notes && <Card>{c.notes}</Card>}
      <Tabs value={tab} onChange={setTab} tabs={[{ value: "invoices", label: "Invoices" }, { value: "payments", label: "Payments" }, { value: "statement", label: "Statement" }]} />
      {tab === "invoices" && <Card bodyClass=""><DataTable columns={invCols} data={c.invoices} onRowClick={(r) => nav(`/invoices/${r.id}`)} rowClass={(r) => (r.status === "voided" ? "voided" : "")} /></Card>}
      {tab === "payments" && <Card bodyClass=""><DataTable columns={payCols} data={c.payments} rowClass={(r) => (r.is_voided ? "voided" : "")} /></Card>}
      {tab === "statement" && <Statement path={`/customers/${id}/statement/`} name={c.name} />}

      {editing && <CustomerForm initial={c} onClose={() => setEditing(false)} onSaved={() => { setEditing(false); refetch(); invalidate("/customers"); }} />}
      {paying && (
        <PaymentModal title={`Payment from ${c.name}`} maxAmount={Math.max(0, Number(c.balance))} onClose={() => setPaying(false)}
          onSubmit={async (v) => {
            try {
              await api.post(`/customers/${id}/payments/`, v);
              toast.ok("Payment recorded against the oldest open invoices");
              setPaying(false);
              refetch();
              invalidate("/customers", "/invoices", "/cash-book", "/dashboard");
            } catch (e) { toast.error(e); }
          }} />
      )}
    </div>
  );
}
