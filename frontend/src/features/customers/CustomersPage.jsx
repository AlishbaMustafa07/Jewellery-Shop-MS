import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, fieldErrors } from "../../api/client";
import { useApi, useInvalidate } from "../../api/hooks";
import DataTable from "../../components/DataTable";
import { Button, Card, ErrorBox, ExportButtons, Input, Modal, NumInput, PageHead, Tabs, TextArea, useForm, useToast } from "../../components/ui";
import { useDebounce, usePermissions } from "../../hooks";
import { date, pkr } from "../../utils/format";

export function CustomerForm({ initial, onClose, onSaved }) {
  const toast = useToast();
  const perms = usePermissions();
  const f = useForm(initial || { name: "", phone: "", address: "", notes: "", opening_balance: "0" });
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true);
    try {
      const body = { name: f.values.name, phone: f.values.phone, address: f.values.address, notes: f.values.notes, opening_balance: f.values.opening_balance || "0" };
      const { data } = initial?.id ? await api.patch(`/customers/${initial.id}/`, body) : await api.post("/customers/", body);
      toast.ok("Customer saved");
      onSaved?.(data);
    } catch (e) {
      f.setErrors(fieldErrors(e));
      toast.error(e);
    } finally { setBusy(false); }
  };
  return (
    <Modal title={initial?.id ? "Edit customer" : "New customer"} onClose={onClose}
      footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" disabled={busy || !f.values.name} onClick={save}>Save</Button></>}>
      <div className="form-grid">
        <Input label="Name" className="span-2" {...f.bind("name")} autoFocus />
        <Input label="Phone" {...f.bind("phone")} />
        {(perms.view_private || !initial?.id) && <NumInput label="Opening balance (old books)" {...f.bind("opening_balance")} hint="Positive = customer owes shop" />}
        <TextArea label="Address" className="span-all" {...f.bind("address")} />
        <TextArea label="Notes" className="span-all" {...f.bind("notes")} />
      </div>
    </Modal>
  );
}

export default function CustomersPage() {
  const nav = useNavigate();
  const invalidate = useInvalidate();
  const [sp, setSp] = useSearchParams();
  const [tab, setTab] = useState("all");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [ordering, setOrdering] = useState("name");
  const [adding, setAdding] = useState(!!sp.get("new"));
  const q = useDebounce(search);
  useEffect(() => setPage(1), [q, tab]);
  const { data, isFetching, error } = useApi(tab === "all" ? "/customers/" : null, { search: q, page, ordering });
  const { data: reminders, isFetching: rf } = useApi(tab === "reminders" ? "/customers/balance-reminders/" : null);

  const columns = [
    { key: "name", label: "Name", sort: "name", render: (r) => <span className="strong">{r.name}</span> },
    { key: "phone", label: "Phone" },
    { key: "address", label: "Address", className: "hide-mobile" },
    { key: "balance", label: "Balance", num: true, sort: "balance", render: (r) => <span style={{ color: Number(r.balance) > 0 ? "var(--warn)" : undefined }}>{pkr(r.balance)}</span> },
    { key: "created_at", label: "Since", className: "hide-mobile", sort: "created_at", render: (r) => date(r.created_at?.slice(0, 10)) },
  ];
  const remCols = [
    { key: "name", label: "Customer", render: (r) => <span className="strong">{r.name}</span> },
    { key: "phone", label: "Phone", render: (r) => r.phone ? <a href={`tel:${r.phone}`} onClick={(e) => e.stopPropagation()}>{r.phone}</a> : "—" },
    { key: "balance", label: "Balance", num: true, render: (r) => pkr(r.balance) },
    { key: "oldest_open", label: "Oldest open", render: (r) => date(r.oldest_open) },
    { key: "days_outstanding", label: "Days", num: true },
    { key: "last_payment", label: "Last payment", className: "hide-mobile", render: (r) => date(r.last_payment) },
  ];

  return (
    <div className="stack">
      <PageHead title="Customers"><Button variant="primary" onClick={() => setAdding(true)}>Add customer</Button></PageHead>
      <Tabs value={tab} onChange={setTab} tabs={[{ value: "all", label: "All customers" }, { value: "reminders", label: "Balance reminders" }]} />
      {tab === "all" ? (
        <>
          <Input placeholder="Search name, phone or address…" value={search} onChange={(e) => setSearch(e.target.value)} autoFocus />
          <ErrorBox error={error} />
          <Card bodyClass="">
            <DataTable columns={columns} data={data} loading={isFetching} page={page} setPage={setPage} ordering={ordering}
              setOrdering={setOrdering} onRowClick={(r) => nav(`/customers/${r.id}`)} />
          </Card>
        </>
      ) : (
        <Card title="Customers with outstanding balance (oldest first)" bodyClass="" actions={<ExportButtons path="/customers/balance-reminders/" name="balance-reminders" />}>
          <DataTable columns={remCols} data={reminders || []} loading={rf} onRowClick={(r) => nav(`/customers/${r.id}`)} empty="No outstanding balances." />
        </Card>
      )}
      {adding && (
        <CustomerForm onClose={() => { setAdding(false); setSp({}); }}
          onSaved={(c) => { invalidate("/customers"); setAdding(false); nav(`/customers/${c.id}`); }} />
      )}
    </div>
  );
}
