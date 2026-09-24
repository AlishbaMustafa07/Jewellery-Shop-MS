import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, openPrintable } from "../../api/client";
import { useApi, useInvalidate } from "../../api/hooks";
import { Alert, Badge, Button, Card, ConfirmReason, ErrorBox, Loading, Modal, NumInput, PageHead, Select, Input, useToast } from "../../components/ui";
import { usePermissions } from "../../hooks";
import { date, dateTime, label, pasa, pkr, wt } from "../../utils/format";

export function PaymentModal({ title, maxAmount, allowAdvance, onClose, onSubmit }) {
  const [v, setV] = useState({ method: "cash", amount: maxAmount ? String(Math.round(maxAmount)) : "", reference: "", notes: "" });
  const [busy, setBusy] = useState(false);
  const methods = ["cash", "bank", "card", ...(allowAdvance ? ["advance"] : [])];
  return (
    <Modal title={title} onClose={onClose} footer={
      <>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="primary" disabled={busy || !(Number(v.amount) > 0)} onClick={async () => {
          setBusy(true);
          try { await onSubmit(v); } finally { setBusy(false); }
        }}>{busy ? "Saving…" : "Record payment"}</Button>
      </>
    }>
      <div className="form-grid">
        <Select label="Method" value={v.method} onChange={(e) => setV({ ...v, method: e.target.value })}
          options={methods.map((m) => ({ value: m, label: m === "advance" ? "Adjust from advance" : label(m) }))} />
        <NumInput label="Amount" value={v.amount} onChange={(e) => setV({ ...v, amount: e.target.value })} autoFocus />
        <Input label="Reference" value={v.reference} onChange={(e) => setV({ ...v, reference: e.target.value })} />
        <Input label="Notes" value={v.notes} onChange={(e) => setV({ ...v, notes: e.target.value })} />
      </div>
    </Modal>
  );
}

export default function InvoiceDetailPage() {
  const { id } = useParams();
  const perms = usePermissions();
  const toast = useToast();
  const invalidate = useInvalidate();
  const { data: inv, isLoading, error, refetch } = useApi(`/invoices/${id}/`);
  const [paying, setPaying] = useState(false);
  const [voiding, setVoiding] = useState(false);
  const [busy, setBusy] = useState(false);
  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  const voided = inv.status === "voided";

  const refresh = () => {
    refetch();
    invalidate("/invoices", "/customers", "/dashboard", "/cash-book", "/stock");
  };

  return (
    <div className="stack">
      <PageHead title={<span className="mono">{inv.number}</span>} subtitle={`${date(inv.date)} · ${inv.customer_display} · by ${inv.salesperson_name || "—"}`}>
        <Badge>{inv.status}</Badge>
        <Button onClick={() => openPrintable(`/invoices/${id}/receipt/`, { size: "a4" })}>Print A4</Button>
        <Button onClick={() => openPrintable(`/invoices/${id}/receipt/`, { size: "80mm" })}>Print 80mm</Button>
        {!voided && Number(inv.balance) > 0 && <Button variant="primary" onClick={() => setPaying(true)}>Take payment</Button>}
        {!voided && perms.void_invoice && <Button variant="danger" onClick={() => setVoiding(true)}>Void</Button>}
      </PageHead>
      {voided && <Alert kind="error">Voided {dateTime(inv.voided_at)} by {inv.voided_by_name}: {inv.void_reason}</Alert>}

      <Card title="Items" bodyClass="table-wrap">
        <table className="table">
          <thead><tr><th>Item</th><th className="num">Weight</th><th className="num">Pasa</th><th className="num">Gold value</th><th className="num">Making</th><th className="num">Stone</th><th className="num">Total</th>{perms.view_profit && <th className="num">Cost</th>}{perms.view_profit && <th className="num">Profit</th>}</tr></thead>
          <tbody>
            {inv.lines.map((l) => (
              <tr key={l.id}>
                <td>{l.stock_item ? <Link to={`/stock/${l.stock_item}`} className="mono strong">{l.stock_code}</Link> : null} {l.category || l.description}</td>
                <td className="num">{wt(l.weight)}</td>
                <td className="num">{pasa(l.pasa)}</td>
                <td className="num">{pkr(l.gold_value)}</td>
                <td className="num">{pkr(l.making_charges)}{l.making_mode !== "fixed" && <div className="small muted">{l.making_rate} {label(l.making_mode)}</div>}</td>
                <td className="num">{pkr(l.stone_value)}</td>
                <td className="num strong">{pkr(l.line_total)}</td>
                {perms.view_profit && <td className="num">{pkr(l.purchase_cost)}</td>}
                {perms.view_profit && <td className="num">{pkr(l.profit)}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <div className="grid grid-2">
        <Card title="Totals" bodyClass="">
          <table className="table"><tbody>
            <tr><td>Sell rate / tola</td><td className="num">{pkr(inv.sale_rate)}</td></tr>
            <tr><td>Subtotal</td><td className="num">{pkr(inv.subtotal)}</td></tr>
            <tr><td>Discount</td><td className="num">− {pkr(inv.discount)}</td></tr>
            <tr><td className="strong">Net amount</td><td className="num strong">Rs {pkr(inv.net_amount)}</td></tr>
            {Number(inv.old_gold_credit) > 0 && <tr><td>Old gold credit</td><td className="num">− {pkr(inv.old_gold_credit)}</td></tr>}
            <tr><td>Paid (incl. old gold)</td><td className="num">{pkr(inv.paid_amount)}</td></tr>
            <tr><td className="strong">Balance</td><td className="num strong">Rs {pkr(inv.balance)}</td></tr>
            {perms.view_profit && inv.profit !== null && <tr><td>Profit (after discount)</td><td className="num">{pkr(inv.profit)}</td></tr>}
            {inv.legacy_book && <tr><td>Legacy ref</td><td className="num">Book {inv.legacy_book} / Page {inv.legacy_page}</td></tr>}
          </tbody></table>
          {inv.customer && <div className="card-body"><Link to={`/customers/${inv.customer}`}>Open customer account →</Link></div>}
        </Card>
        <div className="stack">
          <Card title="Payments" bodyClass="">
            <table className="table"><tbody>
              {inv.payments.map((p) => (
                <tr key={p.id} className={p.is_voided ? "voided" : ""}>
                  <td>{date(p.date)}</td><td>{p.method === "advance" ? "From advance" : label(p.method)} <span className="muted small">{p.reference}</span></td>
                  <td className="small muted">{p.cash_account}</td><td className="num">{pkr(p.amount)}</td>
                </tr>
              ))}
              {!inv.payments.length && <tr><td className="empty">No payments.</td></tr>}
            </tbody></table>
          </Card>
          {inv.old_gold.length > 0 && (
            <Card title="Old gold received" bodyClass="">
              <table className="table"><tbody>
                {inv.old_gold.map((o) => (
                  <tr key={o.id}><td>{o.description || "Old gold"}</td><td className="num">{wt(o.weight)} g @ {o.ratti_kaat}</td>
                    <td className="num">{pkr(o.value)}</td><td><Badge>{o.status}</Badge></td></tr>
                ))}
              </tbody></table>
            </Card>
          )}
          {inv.notes && <Card title="Notes">{inv.notes}</Card>}
        </div>
      </div>

      {paying && (
        <PaymentModal title={`Payment on ${inv.number}`} maxAmount={Number(inv.balance)} allowAdvance={!!inv.customer}
          onClose={() => setPaying(false)}
          onSubmit={async (v) => {
            try {
              await api.post(`/invoices/${id}/payments/`, v);
              toast.ok("Payment recorded");
              setPaying(false);
              refresh();
            } catch (e) { toast.error(e); }
          }} />
      )}
      {voiding && (
        <ConfirmReason title={`Void ${inv.number}?`} busy={busy} confirmLabel="Void invoice"
          prompt="Items go back into stock, payments are reversed in the cash book, and the customer balance is corrected."
          onClose={() => setVoiding(false)}
          onConfirm={async (reason) => {
            setBusy(true);
            try {
              await api.post(`/invoices/${id}/void/`, { reason });
              toast.ok("Invoice voided");
              setVoiding(false);
              refresh();
            } catch (e) { toast.error(e); } finally { setBusy(false); }
          }} />
      )}
    </div>
  );
}
