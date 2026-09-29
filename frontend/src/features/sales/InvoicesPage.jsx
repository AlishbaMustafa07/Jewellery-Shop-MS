import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useApi } from "../../api/hooks";
import DataTable from "../../components/DataTable";
import { Badge, Card, ErrorBox, Input, PageHead, Select } from "../../components/ui";
import { useDebounce } from "../../hooks";
import { date, pkr } from "../../utils/format";

export default function InvoicesPage() {
  const nav = useNavigate();
  const [search, setSearch] = useState("");
  const [f, setF] = useState({ status: "", date_from: "", date_to: "", has_balance: "" });
  const [page, setPage] = useState(1);
  const [ordering, setOrdering] = useState("");
  const q = useDebounce(search);
  useEffect(() => setPage(1), [q, f]);
  const { data, isFetching, error } = useApi("/invoices/", { search: q, ...f, page, ordering });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const columns = [
    { key: "number", label: "Invoice", sort: "number", render: (r) => <span className="mono strong">{r.number}</span> },
    { key: "date", label: "Date", sort: "date", render: (r) => date(r.date) },
    { key: "customer_display", label: "Customer" },
    { key: "line_count", label: "Items", num: true, className: "hide-mobile" },
    { key: "net_amount", label: "Net", num: true, sort: "net_amount", render: (r) => pkr(r.net_amount) },
    { key: "paid_amount", label: "Paid", num: true, className: "hide-mobile", render: (r) => pkr(r.paid_amount) },
    { key: "balance", label: "Balance", num: true, sort: "balance", render: (r) => pkr(r.balance) },
    { key: "salesperson_name", label: "By", className: "hide-mobile" },
    { key: "status", label: "Status", render: (r) => <Badge>{r.status}</Badge> },
  ];

  return (
    <div className="stack">
      <PageHead title="Invoices"><Link className="btn primary" to="/sales/new">New sale</Link></PageHead>
      <Card>
        <div className="form-grid">
          <Input label="Search" className="span-2" placeholder="Invoice no., customer, phone, item code…" value={search} onChange={(e) => setSearch(e.target.value)} />
          <Select label="Status" value={f.status} onChange={set("status")} options={["open", "partial", "paid", "voided"]} placeholder="All" />
          <Select label="Balance" value={f.has_balance} onChange={set("has_balance")} placeholder="Any"
            options={[{ value: "true", label: "Outstanding only" }, { value: "false", label: "Fully paid" }]} />
          <Input type="date" label="From" value={f.date_from} onChange={set("date_from")} />
          <Input type="date" label="To" value={f.date_to} onChange={set("date_to")} />
        </div>
      </Card>
      <ErrorBox error={error} />
      <Card bodyClass="">
        <DataTable columns={columns} data={data} loading={isFetching} page={page} setPage={setPage} ordering={ordering}
          setOrdering={setOrdering} onRowClick={(r) => nav(`/invoices/${r.id}`)} rowClass={(r) => (r.status === "voided" ? "voided" : "")} />
      </Card>
    </div>
  );
}
