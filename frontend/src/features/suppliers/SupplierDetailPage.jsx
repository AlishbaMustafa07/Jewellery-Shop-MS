import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { useApi, useInvalidate } from "../../api/hooks";
import DataTable from "../../components/DataTable";
import { Badge, Button, Card, ConfirmReason, ErrorBox, Input, Loading, Modal, NumInput, PageHead, Select, Stat, Tabs, useToast } from "../../components/ui";
import { usePermissions, useSettings } from "../../hooks";
import { date, label, pasa, pkr, todayISO, wt } from "../../utils/format";
import { Statement } from "../customers/CustomerDetailPage";
import { SupplierForm } from "./SuppliersPage";

function TxnModal({ kind, supplier, onClose, onDone }) {
  const toast = useToast();
  const { data: settings } = useSettings();
  const [v, setV] = useState({ amount: "", method: "cash", cash_account: "", date: todayISO(), gold_pasa: "", notes: "", type: "adjustment" });
  const submit = async () => {
    try {
      const body = { ...v, gold_pasa: v.gold_pasa || null };
      if (kind === "payment") await api.post(`/suppliers/${supplier.id}/payments/`, body);
      else await api.post(`/suppliers/${supplier.id}/adjustments/`, body);
      toast.ok("Saved");
      onDone();
    } catch (e) { toast.error(e); }
  };
  return (
    <Modal title={kind === "payment" ? `Pay ${supplier.name}` : `Add charge for ${supplier.name}`} onClose={onClose}
      footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" disabled={!(Number(v.amount) > 0)} onClick={submit}>Save</Button></>}>
      <div className="form-grid">
        {kind === "payment" ? (
          <>
            <Select label="Method" value={v.method} onChange={(e) => setV({ ...v, method: e.target.value })} options={["cash", "bank", "gold"]} />
            {v.method !== "gold" && <Select label="From account" value={v.cash_account} onChange={(e) => setV({ ...v, cash_account: e.target.value })} options={settings?.cash_accounts || []} placeholder="Default" />}
          </>
        ) : (
          <Select label="Type" value={v.type} onChange={(e) => setV({ ...v, type: e.target.value })} options={[{ value: "labour", label: "Karigar labour" }, { value: "adjustment", label: "Adjustment (+)" }]} />
        )}
        <NumInput label="Amount (Rs)" value={v.amount} onChange={(e) => setV({ ...v, amount: e.target.value })} autoFocus />
        <NumInput label="Gold pasa (optional)" value={v.gold_pasa} onChange={(e) => setV({ ...v, gold_pasa: e.target.value })} />
        <Input type="date" label="Date" value={v.date} onChange={(e) => setV({ ...v, date: e.target.value })} />
        <Input label="Notes" className="span-2" value={v.notes} onChange={(e) => setV({ ...v, notes: e.target.value })} />
      </div>
    </Modal>
  );
}

export default function SupplierDetailPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const perms = usePermissions();
  const toast = useToast();
  const invalidate = useInvalidate();
  const [tab, setTab] = useState("ledger");
  const [modal, setModal] = useState(null);
  const [voiding, setVoiding] = useState(null);
  const { data: s, isLoading, error, refetch } = useApi(`/suppliers/${id}/`);
  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  const done = () => { setModal(null); refetch(); invalidate("/suppliers", "/cash-book"); };
  const backOffice = perms.day_close;

  const txnCols = [
    { key: "date", label: "Date", render: (r) => date(r.date) },
    { key: "type", label: "Type", render: (r) => label(r.type) },
    { key: "stock_code", label: "Item", className: "mono" },
    { key: "notes", label: "Notes", className: "hide-mobile" },
    { key: "gold_pasa", label: "Pasa", num: true, render: (r) => (r.gold_pasa ? pasa(r.gold_pasa) : "") },
    { key: "amount", label: "Amount", num: true, render: (r) => pkr(r.amount) },
    { key: "x", label: "", render: (r) => (!r.is_voided && r.type !== "purchase" && perms.void_invoice ? <Button size="sm" variant="ghost" onClick={() => setVoiding(r)}>Void</Button> : r.is_voided ? <Badge kind="danger">voided</Badge> : null) },
  ];
  const itemCols = [
    { key: "code", label: "Code", render: (r) => <span className="mono strong">{r.code}</span> },
    { key: "category", label: "Category" },
    { key: "gross_weight", label: "Gross", num: true, render: (r) => wt(r.gross_weight) },
    { key: "pasa", label: "Pasa", num: true, render: (r) => pasa(r.pasa) },
    perms.view_profit && { key: "total_cost", label: "Cost", num: true, render: (r) => pkr(r.total_cost) },
    { key: "purchase_date", label: "Purchased", render: (r) => date(r.purchase_date) },
    { key: "status", label: "Status", render: (r) => <Badge>{r.status}</Badge> },
  ].filter(Boolean);

  return (
    <div className="stack">
      <PageHead title={s.name} subtitle={`${label(s.type)}${s.phone ? " · " + s.phone : ""}`}>
        {backOffice && <Button onClick={() => setModal("edit")}>Edit</Button>}
        {perms.void_invoice && <Button onClick={() => setModal("charge")}>Add charge</Button>}
        {backOffice && <Button variant="primary" onClick={() => setModal("payment")}>Make payment</Button>}
      </PageHead>
      <div className="grid grid-3">
        <Stat label="Shop owes" value={`Rs ${pkr(s.balance)}`} />
        <Stat label="Items supplied" value={s.item_count} />
        <Stat label="Opening balance" value={`Rs ${pkr(s.opening_balance)}`} />
      </div>
      <Tabs value={tab} onChange={setTab} tabs={[{ value: "ledger", label: "Ledger" }, { value: "items", label: "Items" }, { value: "statement", label: "Statement" }]} />
      {tab === "ledger" && <Card bodyClass=""><DataTable columns={txnCols} data={s.transactions} rowClass={(r) => (r.is_voided ? "voided" : "")} /></Card>}
      {tab === "items" && <Card bodyClass=""><DataTable columns={itemCols} data={s.items} onRowClick={(r) => nav(`/stock/${r.id}`)} /></Card>}
      {tab === "statement" && <Statement path={`/suppliers/${id}/statement/`} name={s.name} />}
      {modal === "edit" && <SupplierForm initial={s} onClose={() => setModal(null)} onSaved={done} />}
      {(modal === "payment" || modal === "charge") && <TxnModal kind={modal} supplier={s} onClose={() => setModal(null)} onDone={done} />}
      {voiding && (
        <ConfirmReason title="Void ledger entry?" prompt={`${label(voiding.type)} of Rs ${pkr(voiding.amount)} will be reversed.`}
          onClose={() => setVoiding(null)}
          onConfirm={async (reason) => {
            try {
              await api.post(`/suppliers/${id}/transactions/${voiding.id}/void/`, { reason });
              setVoiding(null);
              done();
            } catch (e) { toast.error(e); }
          }} />
      )}
    </div>
  );
}
