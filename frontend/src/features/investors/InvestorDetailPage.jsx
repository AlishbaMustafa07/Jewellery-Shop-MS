import { useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../../api/client";
import { useApi, useInvalidate } from "../../api/hooks";
import DataTable from "../../components/DataTable";
import { Badge, Button, Card, ConfirmReason, DateRange, ErrorBox, ExportButtons, Input, Loading, Modal, NumInput, PageHead, Select, Stat, useToast } from "../../components/ui";
import { useSettings } from "../../hooks";
import { date, label, monthStartISO, pkr, todayISO } from "../../utils/format";
import { InvestorForm } from "./InvestorsPage";

function TxnModal({ investor, onClose, onDone, preset }) {
  const toast = useToast();
  const { data: settings } = useSettings();
  const [v, setV] = useState({ type: "investment", date: todayISO(), amount: "", cash_account: "shop_cash", notes: "", period_from: "", period_to: "", ...preset });
  const save = async () => {
    try {
      await api.post(`/investors/${investor.id}/transactions/`, { ...v, period_from: v.period_from || null, period_to: v.period_to || null });
      toast.ok("Recorded");
      onDone();
    } catch (e) { toast.error(e); }
  };
  return (
    <Modal title={`Transaction — ${investor.name}`} onClose={onClose}
      footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" disabled={!(Number(v.amount) > 0)} onClick={save}>Save</Button></>}>
      <div className="form-grid">
        <Select label="Type" value={v.type} onChange={(e) => setV({ ...v, type: e.target.value })} options={["investment", "withdrawal", "profit_paid"]} />
        <Input type="date" label="Date" value={v.date} onChange={(e) => setV({ ...v, date: e.target.value })} />
        <NumInput label="Amount" value={v.amount} onChange={(e) => setV({ ...v, amount: e.target.value })} autoFocus />
        <Select label="Cash account" value={v.cash_account} onChange={(e) => setV({ ...v, cash_account: e.target.value })} options={settings?.cash_accounts || ["shop_cash"]} />
        {v.type === "profit_paid" && (
          <>
            <Input type="date" label="Period from" value={v.period_from} onChange={(e) => setV({ ...v, period_from: e.target.value })} />
            <Input type="date" label="Period to" value={v.period_to} onChange={(e) => setV({ ...v, period_to: e.target.value })} />
          </>
        )}
        <Input label="Notes" className="span-2" value={v.notes} onChange={(e) => setV({ ...v, notes: e.target.value })} />
      </div>
    </Modal>
  );
}

export default function InvestorDetailPage() {
  const { id } = useParams();
  const toast = useToast();
  const invalidate = useInvalidate();
  const [modal, setModal] = useState(null);
  const [voiding, setVoiding] = useState(null);
  const [range, setRange] = useState({ from: monthStartISO(), to: todayISO() });
  const { data: inv, isLoading, error, refetch } = useApi(`/investors/${id}/`);
  const { data: est } = useApi(`/investors/${id}/profit-estimate/`, { date_from: range.from, date_to: range.to });
  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  const done = () => { setModal(null); refetch(); invalidate("/investors", "/cash-book"); };

  return (
    <div className="stack">
      <PageHead title={inv.name} subtitle={`Share ${inv.share_percent}% · Ref ${inv.reference || "—"} · Book ${inv.book_no || "—"}/${inv.page_no || "—"}`}>
        <ExportButtons path={`/investors/${id}/statement/`} name={`investor-${inv.name}`} formats={["xlsx", "html"]} />
        <Button onClick={() => setModal({ kind: "edit" })}>Edit</Button>
        <Button variant="primary" onClick={() => setModal({ kind: "txn" })}>Add transaction</Button>
      </PageHead>
      <div className="grid grid-4">
        <Stat label="Capital" value={`Rs ${pkr(inv.totals.capital)}`} />
        <Stat label="Invested" value={pkr(inv.totals.invested)} />
        <Stat label="Withdrawn" value={pkr(inv.totals.withdrawn)} />
        <Stat label="Profit paid" value={pkr(inv.totals.profit_paid)} />
      </div>
      <Card title={<DateRange from={range.from} to={range.to} onChange={setRange} />}>
        <h3>Profit estimate for this period</h3>
        {est && (
          <div className="grid grid-3">
            <Stat label="Shop net profit" value={pkr(est.shop_net_profit)} />
            <Stat label={`${est.share_percent}% of net profit`} value={pkr(est.share_of_net_profit)}
              hint={<Button size="sm" onClick={() => setModal({ kind: "txn", preset: { type: "profit_paid", amount: est.share_of_net_profit, period_from: range.from, period_to: range.to } })}>Pay this</Button>} />
            <Stat label={`${est.share_percent}% of capital × ${est.months} month(s)`} value={pkr(est.percent_of_capital_per_month)}
              hint={<Button size="sm" onClick={() => setModal({ kind: "txn", preset: { type: "profit_paid", amount: est.percent_of_capital_per_month, period_from: range.from, period_to: range.to } })}>Pay this</Button>} />
          </div>
        )}
        <p className="small muted">Two methods are shown until the owner confirms which one the old Profit sheet used.</p>
      </Card>
      <Card title="Transactions" bodyClass="">
        <DataTable data={inv.transactions} rowClass={(r) => (r.is_voided ? "voided" : "")} columns={[
          { key: "date", label: "Date", render: (r) => date(r.date) },
          { key: "type", label: "Type", render: (r) => label(r.type) },
          { key: "amount", label: "Amount", num: true, render: (r) => pkr(r.amount) },
          { key: "cash_account", label: "Account", className: "hide-mobile" },
          { key: "period", label: "Period", className: "hide-mobile", render: (r) => (r.period_from ? `${date(r.period_from)} – ${date(r.period_to)}` : "") },
          { key: "notes", label: "Notes", className: "hide-mobile" },
          { key: "x", label: "", render: (r) => (r.is_voided ? <Badge kind="danger">voided</Badge> : <Button size="sm" variant="ghost" onClick={() => setVoiding(r)}>Void</Button>) },
        ]} />
      </Card>
      {modal?.kind === "edit" && <InvestorForm initial={inv} onClose={() => setModal(null)} onSaved={done} />}
      {modal?.kind === "txn" && <TxnModal investor={inv} preset={modal.preset} onClose={() => setModal(null)} onDone={done} />}
      {voiding && (
        <ConfirmReason title="Void transaction?" prompt={`${label(voiding.type)} Rs ${pkr(voiding.amount)}`} onClose={() => setVoiding(null)}
          onConfirm={async (reason) => {
            try { await api.post(`/investors/${id}/transactions/${voiding.id}/void/`, { reason }); setVoiding(null); done(); } catch (e) { toast.error(e); }
          }} />
      )}
    </div>
  );
}
