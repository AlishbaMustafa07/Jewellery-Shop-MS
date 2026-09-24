import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, fieldErrors } from "../../api/client";
import { useApi, useInvalidate } from "../../api/hooks";
import DataTable from "../../components/DataTable";
import { Button, Card, Input, Modal, NumInput, PageHead, TextArea, useForm, useToast } from "../../components/ui";
import { pkr } from "../../utils/format";

export function InvestorForm({ initial, onClose, onSaved }) {
  const toast = useToast();
  const f = useForm(initial || { name: "", phone: "", reference: "", book_no: "", page_no: "", share_percent: "0", notes: "", is_active: true });
  const save = async () => {
    try {
      const { totals, transactions, created_at, id, ...body } = f.values; // eslint-disable-line no-unused-vars
      const { data } = initial?.id ? await api.patch(`/investors/${initial.id}/`, body) : await api.post("/investors/", body);
      toast.ok("Saved");
      onSaved(data);
    } catch (e) { f.setErrors(fieldErrors(e)); toast.error(e); }
  };
  return (
    <Modal title={initial?.id ? "Edit investor" : "New investor"} onClose={onClose}
      footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" disabled={!f.values.name} onClick={save}>Save</Button></>}>
      <div className="form-grid">
        <Input label="Name" className="span-2" {...f.bind("name")} autoFocus />
        <Input label="Phone" {...f.bind("phone")} />
        <Input label="Reference" {...f.bind("reference")} />
        <NumInput label="Share %" {...f.bind("share_percent")} />
        <Input label="Book no." {...f.bind("book_no")} />
        <Input label="Page no." {...f.bind("page_no")} />
        <TextArea label="Notes" className="span-all" {...f.bind("notes")} />
      </div>
    </Modal>
  );
}

export default function InvestorsPage() {
  const nav = useNavigate();
  const invalidate = useInvalidate();
  const [adding, setAdding] = useState(false);
  const { data, isFetching } = useApi("/investors/", { page_size: 200 });
  const rows = data?.results || [];
  const sum = (k) => rows.reduce((a, r) => a + Number(r.totals[k]), 0);
  return (
    <div className="stack">
      <PageHead title="Investors" subtitle="Owner only."><Button variant="primary" onClick={() => setAdding(true)}>Add investor</Button></PageHead>
      <Card bodyClass="">
        <DataTable data={data} loading={isFetching} onRowClick={(r) => nav(`/investors/${r.id}`)}
          footer={{ name: "Total", capital: pkr(sum("capital")), profit: pkr(sum("profit_paid")) }}
          columns={[
            { key: "name", label: "Name", render: (r) => <span className="strong">{r.name}</span> },
            { key: "reference", label: "Reference" },
            { key: "share_percent", label: "Share %", num: true },
            { key: "capital", label: "Capital", num: true, render: (r) => pkr(r.totals.capital) },
            { key: "profit", label: "Profit paid", num: true, render: (r) => pkr(r.totals.profit_paid) },
            { key: "book", label: "Book / page", className: "hide-mobile", render: (r) => [r.book_no, r.page_no].filter(Boolean).join(" / ") },
          ]} />
      </Card>
      {adding && <InvestorForm onClose={() => setAdding(false)} onSaved={(d) => { invalidate("/investors"); nav(`/investors/${d.id}`); }} />}
    </div>
  );
}
