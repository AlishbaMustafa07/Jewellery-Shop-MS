import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, fieldErrors } from "../../api/client";
import { useApi, useInvalidate } from "../../api/hooks";
import DataTable from "../../components/DataTable";
import { Button, Card, ErrorBox, Input, Modal, NumInput, PageHead, Select, TextArea, useForm, useToast } from "../../components/ui";
import { useDebounce, usePermissions } from "../../hooks";
import { label, pkr } from "../../utils/format";

export function SupplierForm({ initial, onClose, onSaved }) {
  const toast = useToast();
  const f = useForm(initial || { name: "", type: "supplier", phone: "", notes: "", opening_balance: "0" });
  const save = async () => {
    try {
      const body = { name: f.values.name, type: f.values.type, phone: f.values.phone, notes: f.values.notes, opening_balance: f.values.opening_balance || "0" };
      const { data } = initial?.id ? await api.patch(`/suppliers/${initial.id}/`, body) : await api.post("/suppliers/", body);
      toast.ok("Saved");
      onSaved(data);
    } catch (e) { f.setErrors(fieldErrors(e)); toast.error(e); }
  };
  return (
    <Modal title={initial?.id ? "Edit supplier" : "New supplier / karigar"} onClose={onClose}
      footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" disabled={!f.values.name} onClick={save}>Save</Button></>}>
      <div className="form-grid">
        <Input label="Name" className="span-2" {...f.bind("name")} autoFocus />
        <Select label="Type" {...f.bind("type")} options={["supplier", "karigar"]} />
        <Input label="Phone" {...f.bind("phone")} />
        <NumInput label="Opening balance" {...f.bind("opening_balance")} hint="Positive = shop owes them" />
        <TextArea label="Notes" className="span-all" {...f.bind("notes")} />
      </div>
    </Modal>
  );
}

export default function SuppliersPage() {
  const nav = useNavigate();
  const invalidate = useInvalidate();
  const perms = usePermissions();
  const [search, setSearch] = useState("");
  const [type, setType] = useState("");
  const [adding, setAdding] = useState(false);
  const q = useDebounce(search);
  const { data, isFetching, error } = useApi("/suppliers/", { search: q, type, page_size: 200 });
  const columns = [
    { key: "name", label: "Name", render: (r) => <span className="strong">{r.name}</span> },
    { key: "type", label: "Type", render: (r) => label(r.type) },
    { key: "phone", label: "Phone" },
    { key: "item_count", label: "Items", num: true },
    { key: "balance", label: "Shop owes", num: true, render: (r) => pkr(r.balance) },
  ];
  return (
    <div className="stack">
      <PageHead title="Suppliers & karigar">{perms.day_close && <Button variant="primary" onClick={() => setAdding(true)}>Add</Button>}</PageHead>
      <div className="form-grid">
        <Input label="Search" className="span-2" value={search} onChange={(e) => setSearch(e.target.value)} />
        <Select label="Type" value={type} onChange={(e) => setType(e.target.value)} options={["supplier", "karigar"]} placeholder="All" />
      </div>
      <ErrorBox error={error} />
      <Card bodyClass=""><DataTable columns={columns} data={data} loading={isFetching} onRowClick={(r) => nav(`/suppliers/${r.id}`)} /></Card>
      {adding && <SupplierForm onClose={() => setAdding(false)} onSaved={(s) => { invalidate("/suppliers"); nav(`/suppliers/${s.id}`); }} />}
    </div>
  );
}
