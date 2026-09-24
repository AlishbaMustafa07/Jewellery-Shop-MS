import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useApi } from "../../api/hooks";
import { Alert, Badge, Card, ErrorBox, Loading, PageHead, Stat } from "../../components/ui";
import { usePermissions } from "../../hooks";
import { date, pasa, pkr, toNum } from "../../utils/format";

function SalesBars({ rows }) {
  const [hover, setHover] = useState(null);
  if (!rows?.length) return <div className="empty">No sales in the last 30 days.</div>;
  const max = Math.max(...rows.map((r) => toNum(r.net)), 1);
  const h = hover !== null ? rows[hover] : null;
  return (
    <div>
      <div className="small muted" style={{ minHeight: 18 }} aria-live="polite">
        {h ? <><b style={{ color: "var(--text)" }}>{date(h.date)}</b> · Rs {pkr(h.net)}</> : `Peak day Rs ${pkr(max)}`}
      </div>
      <div className="bars" role="img" aria-label="Daily net sales, last 30 days" onMouseLeave={() => setHover(null)}>
        {rows.map((r, i) => (
          <div key={r.date} className="bar" title={`${date(r.date)}: Rs ${pkr(r.net)}`}
            style={{ height: `${Math.max(2, (toNum(r.net) / max) * 100)}%`, borderRadius: "4px 4px 0 0",
              opacity: hover === null || hover === i ? 0.9 : 0.45 }}
            onMouseEnter={() => setHover(i)} />
        ))}
      </div>
      <div className="gap small muted" style={{ justifyContent: "space-between", marginTop: 4 }}>
        <span>{date(rows[0].date)}</span><span>{date(rows[rows.length - 1].date)}</span>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { data, isLoading, error } = useApi("/dashboard/");
  const p = usePermissions();
  const nav = useNavigate();
  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  const d = data;

  return (
    <div className="stack">
      <PageHead title="Dashboard" subtitle={date(d.date)}>
        <Link className="btn primary" to="/sales/new">New sale</Link>
        <Link className="btn" to="/stock">Search stock</Link>
      </PageHead>

      {!d.gold_rate?.is_today && (
        <Alert kind="warn">
          Today's gold rate has not been entered{d.gold_rate ? ` — using ${date(d.gold_rate.date)}` : ""}.{" "}
          <Link to="/rates">Set it now</Link>
        </Alert>
      )}
      {d.day_locked && <Alert kind="info">Today's cash book is closed.</Alert>}

      <div className="grid grid-4">
        <Stat label="Gold rate (sell / tola)" value={d.gold_rate ? pkr(d.gold_rate.sell) : "—"}
          hint={d.gold_rate ? `Buy ${pkr(d.gold_rate.buy)}` : "Not set"} />
        <Stat label="Today's sales" value={`Rs ${pkr(d.today_sales.net)}`}
          hint={`${d.today_sales.count} invoice(s) · received ${pkr(d.today_sales.received)}`} />
        <Stat label="Cash in hand" value={`Rs ${pkr(d.cash_in_hand)}`}
          hint={Object.entries(d.cash_accounts).filter(([k]) => k !== "shop_cash").map(([k, v]) => `${k} ${pkr(v)}`).join(" · ")} />
        <Stat label="Outstanding (customers)" value={`Rs ${pkr(d.outstanding_receivables)}`}
          hint={`${d.customers_with_balance} customer(s)`} />
        <Stat label="Stock value @ today" value={d.stock.value_at_today ? `Rs ${pkr(d.stock.value_at_today)}` : "—"}
          hint={`${d.stock.items} items · ${pasa(d.stock.gold_pasa)} g pasa${p.view_profit ? ` · cost ${pkr(d.stock.cost)}` : ""}`} />
        <Stat label="Old gold pending refine" value={`${pasa(d.pending_old_gold)} g`} hint="pasa" />
        {d.month && (
          <>
            <Stat label="This month net sales" value={`Rs ${pkr(d.month.net_sales)}`}
              hint={`Gross profit ${pkr(d.month.gross_profit)}`} />
            <Stat label="This month net profit" value={`Rs ${pkr(d.month.net_profit)}`}
              hint={`Expenses ${pkr(d.month.expenses)} · payables ${pkr(d.payables)}`} />
          </>
        )}
      </div>

      <div className="grid grid-2">
        <Card title="Daily sales — last 30 days">
          <SalesBars rows={d.sales_30_days} />
        </Card>
        <Card title="Recent invoices" bodyClass="">
          <table className="table">
            <tbody>
              {d.recent_invoices.map((i) => (
                <tr key={i.id} className="clickable" onClick={() => nav(`/invoices/${i.id}`)}>
                  <td className="mono">{i.number}</td>
                  <td>{i.customer__name || i.customer_name || "Walk-in"}</td>
                  <td className="hide-mobile">{date(i.date)}</td>
                  <td className="num">{pkr(i.net_amount)}</td>
                  <td><Badge>{i.status}</Badge></td>
                </tr>
              ))}
              {!d.recent_invoices.length && <tr><td className="empty">No sales yet.</td></tr>}
            </tbody>
          </table>
        </Card>
      </div>
      <div className="small muted">Shortcuts: Alt+N new sale · Alt+K stock search · Alt+D day close</div>
    </div>
  );
}
