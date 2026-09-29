import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { download } from "../../api/client";
import { useApi } from "../../api/hooks";
import DataTable from "../../components/DataTable";
import { Button, Card, DateRange, ErrorBox, ExportButtons, Loading, NumInput, PageHead, Select, Stat, Tabs, useToast } from "../../components/ui";
import { usePermissions, useRole } from "../../hooks";
import { date, label, monthStartISO, pasa, pkr, todayISO, wt } from "../../utils/format";

function Line({ k, v, strong, indent }) {
  return (
    <tr><td style={{ paddingLeft: indent ? 28 : 10 }} className={strong ? "strong" : ""}>{k}</td><td className={`num ${strong ? "strong" : ""}`}>{pkr(v)}</td></tr>
  );
}

function ProfitLoss({ range }) {
  const { data: d, isLoading, error } = useApi("/reports/profit-loss/", range);
  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  return (
    <div className="stack">
      <div className="grid grid-4">
        <Stat label="Net sales" value={pkr(d.net_sales)} hint={`${d.invoice_count} invoices · discount ${pkr(d.discount)}`} />
        <Stat label="Gross profit" value={pkr(d.gross_profit)} hint={`COGS ${pkr(d.cost_of_goods_sold)}`} />
        <Stat label="Expenses" value={pkr(d.total_expenses)} />
        <Stat label="Net profit" value={pkr(d.net_profit)} hint={`Drawings ${pkr(d.total_drawings)}`} />
      </div>
      <div className="grid grid-2">
        <Card title="Profit & loss statement" bodyClass="" actions={<ExportButtons path="/reports/profit-loss/" params={range} name="profit-loss" />}>
          <table className="table"><tbody>
            <Line k="Net sales" v={d.net_sales} />
            <Line k="Less: cost of goods sold" v={-d.cost_of_goods_sold} />
            <Line k="Gross profit" v={d.gross_profit} strong />
            {d.other_income.map((r) => <Line key={r.head} k={`+ ${r.head}`} v={r.total} indent />)}
            {d.expenses.map((r) => <Line key={r.head} k={`− ${r.head}`} v={-r.total} indent />)}
            <Line k="Net profit" v={d.net_profit} strong />
            {d.drawings.map((r) => <Line key={r.head} k={`Drawings: ${r.head}`} v={-r.total} indent />)}
          </tbody></table>
          <div className="card-body small muted">{d.note}</div>
        </Card>
        <Card title="By category" bodyClass="">
          <DataTable data={d.by_category} columns={[
            { key: "category", label: "Category" },
            { key: "items", label: "Items", num: true },
            { key: "weight", label: "Weight", num: true, render: (r) => wt(r.weight) },
            { key: "sales", label: "Sales", num: true, render: (r) => pkr(r.sales) },
            { key: "cost", label: "Cost", num: true, render: (r) => pkr(r.cost) },
            { key: "profit", label: "Profit", num: true, render: (r) => pkr(r.profit) },
          ]} />
        </Card>
      </div>
    </div>
  );
}

function StockValuation() {
  const perms = usePermissions();
  const nav = useNavigate();
  const [slow, setSlow] = useState("180");
  const { data: d, isLoading, error } = useApi("/reports/stock-valuation/", { slow_days: slow });
  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  return (
    <div className="stack">
      <div className="grid grid-4">
        <Stat label="Items in stock" value={d.totals.items} hint={`${d.totals.pieces} pcs`} />
        <Stat label="Pasa" value={pasa(d.totals.pasa)} hint={`Gross ${wt(d.totals.gross_weight)} g`} />
        {perms.view_profit && <Stat label="At cost" value={pkr(d.totals.cost)} />}
        <Stat label="Gold @ today's rate" value={pkr(d.totals.value_at_today)} hint={d.rate ? `Sell ${pkr(d.rate)} (${date(d.rate_date)})` : "No rate"} />
      </div>
      <Card title="By metal & category" bodyClass="" actions={<ExportButtons path="/reports/stock-valuation/" name="stock-valuation" />}>
        <DataTable data={d.groups} columns={[
          { key: "metal", label: "Metal", render: (r) => label(r.metal) },
          { key: "category", label: "Category" },
          { key: "items", label: "Items", num: true },
          { key: "gross_weight", label: "Gross", num: true, render: (r) => wt(r.gross_weight) },
          { key: "pasa", label: "Pasa", num: true, render: (r) => pasa(r.pasa) },
          perms.view_profit && { key: "cost", label: "Cost", num: true, render: (r) => pkr(r.cost) },
          { key: "value_at_today", label: "@ today", num: true, render: (r) => pkr(r.value_at_today) },
          perms.view_profit && { key: "unrealised_gain", label: "Gain", num: true, render: (r) => pkr(r.unrealised_gain) },
        ].filter(Boolean)} />
      </Card>
      <Card title={`Slow-moving (in stock more than ${slow} days)`} bodyClass=""
        actions={<div style={{ width: 120 }}><NumInput value={slow} onChange={(e) => setSlow(e.target.value)} aria-label="Days" /></div>}>
        <DataTable data={d.slow_moving} onRowClick={(r) => nav(`/stock/${r.id}`)} empty="No slow-moving items." columns={[
          { key: "code", label: "Code", className: "mono" },
          { key: "category", label: "Category" },
          { key: "gross_weight", label: "Gross", num: true, render: (r) => wt(r.gross_weight) },
          { key: "pasa", label: "Pasa", num: true, render: (r) => pasa(r.pasa) },
          perms.view_profit && { key: "total_cost", label: "Cost", num: true, render: (r) => pkr(r.total_cost) },
          { key: "purchase_date", label: "Purchased", render: (r) => date(r.purchase_date) },
        ].filter(Boolean)} />
      </Card>
    </div>
  );
}

function Sales({ range }) {
  const perms = usePermissions();
  const [groupBy, setGroupBy] = useState("day");
  const params = { ...range, group_by: groupBy };
  const { data: d, isLoading, error } = useApi("/reports/sales/", params);
  const cat = groupBy === "category";
  return (
    <div className="stack">
      <div className="gap">
        <Select label="Group by" value={groupBy} onChange={(e) => setGroupBy(e.target.value)} options={["day", "month", "category", "salesperson", "customer"]} />
        <div className="spacer" />
        <ExportButtons path="/reports/sales/" params={params} name={`sales-${groupBy}`} />
      </div>
      <ErrorBox error={error} />
      {isLoading ? <Loading /> : (
        <Card bodyClass="">
          <DataTable data={d.rows} columns={[
            { key: "key", label: label(groupBy) },
            cat ? { key: "items", label: "Items", num: true } : { key: "invoices", label: "Invoices", num: true },
            cat && { key: "weight", label: "Weight", num: true, render: (r) => wt(r.weight) },
            { key: "net", label: "Net sales", num: true, render: (r) => pkr(r.net) },
            !cat && { key: "discount", label: "Discount", num: true, render: (r) => pkr(r.discount) },
            !cat && { key: "received", label: "Received", num: true, render: (r) => pkr(r.received) },
            !cat && { key: "balance", label: "Balance", num: true, render: (r) => pkr(r.balance) },
            cat && perms.view_profit && { key: "profit", label: "Profit", num: true, render: (r) => pkr(r.profit) },
          ].filter(Boolean)}
            footer={{ key: "Total", invoices: d.totals.invoices, net: pkr(d.totals.net), discount: pkr(d.totals.discount), received: pkr(d.totals.received), balance: pkr(d.totals.balance), profit: d.totals.profit !== undefined ? pkr(d.totals.profit) : "" }} />
        </Card>
      )}
    </div>
  );
}

function Expenses({ range }) {
  const { data: d, isLoading, error } = useApi("/reports/expenses/", range);
  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  return (
    <div className="stack">
      <div className="grid grid-4">
        <Stat label="Shop expenses" value={pkr(d.shop_total)} />
        <Stat label="Home" value={pkr(d.home_total)} />
        <Stat label="All expenditure" value={pkr(d.total)} />
      </div>
      <Card title="By head & sub-head" bodyClass="" actions={<ExportButtons path="/reports/expenses/" params={range} name="expenses" />}>
        <DataTable data={d.rows} footer={{ head: "Total", total: pkr(d.total) }} columns={[
          { key: "head", label: "Head" },
          { key: "sub_head", label: "Sub-head" },
          { key: "group", label: "Group", render: (r) => label(r.group) },
          { key: "count", label: "Entries", num: true },
          { key: "total", label: "Total", num: true, render: (r) => pkr(r.total) },
        ]} />
      </Card>
    </div>
  );
}

function AccountSummary({ range }) {
  const { data: d, isLoading, error } = useApi("/reports/account-summary/", range);
  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  const r = d.refine_account, s = d.shop_purchase_account, p = d.profit_retention_account;
  return (
    <div className="stack">
      <p className="small muted">Provisional — the exact meaning of these accounts is an open question for the owner (spec §11).</p>
      <div className="grid grid-3">
        <Card title="Refine account" bodyClass="">
          <table className="table"><tbody>
            <tr><td>Lots in period</td><td className="num">{r.lots}</td></tr>
            <tr><td>Weight sent</td><td className="num">{wt(r.weight_sent)} g</td></tr>
            <tr><td>Pasa expected / returned</td><td className="num">{pasa(r.pasa_expected)} / {pasa(r.pasa_returned)}</td></tr>
            <tr><td>Refining cost</td><td className="num">{pkr(r.cost)}</td></tr>
            <tr><td className="strong">Pool now</td><td className="num strong">{pasa(r.pool.pool_pasa)} pasa</td></tr>
          </tbody></table>
        </Card>
        <Card title="Shop purchase account" bodyClass="">
          <table className="table"><tbody>
            <Line k="Purchased (incl. labour)" v={s.purchased} />
            <Line k="Paid to suppliers" v={s.paid_to_suppliers} />
            <Line k="Returned" v={s.returned} />
            <Line k="Owed to suppliers now" v={s.owed_now} strong />
          </tbody></table>
        </Card>
        <Card title="Profit retention account" bodyClass="">
          <table className="table"><tbody>
            <Line k="Net profit" v={p.net_profit} />
            <Line k="Investor profit paid" v={-p.investor_profit_paid} />
            <Line k="Drawings (home, zakat)" v={-p.drawings} />
            <Line k="Retained" v={p.retained} strong />
          </tbody></table>
        </Card>
      </div>
    </div>
  );
}

export default function ReportsPage() {
  const perms = usePermissions();
  const role = useRole();
  const toast = useToast();
  const [tab, setTab] = useState(perms.view_profit ? "pl" : "stock");
  const [range, setRange] = useState({ from: monthStartISO(), to: todayISO() });
  const params = { date_from: range.from, date_to: range.to };
  const tabs = [
    perms.view_profit && { value: "pl", label: "Profit & loss" },
    { value: "stock", label: "Stock valuation" },
    { value: "sales", label: "Sales" },
    { value: "expenses", label: "Expenses" },
    perms.view_profit && { value: "accounts", label: "Account summary" },
  ].filter(Boolean);
  return (
    <div className="stack">
      <PageHead title="Reports">
        {tab !== "stock" && <DateRange from={range.from} to={range.to} onChange={setRange} />}
        {role === "owner" && (
          <Button onClick={async () => { try { await download("/reports/export/", { type: "full" }, "full-export.xlsx"); } catch (e) { toast.error(e); } }}>
            Download all data (Excel)
          </Button>
        )}
      </PageHead>
      <Tabs tabs={tabs} value={tab} onChange={setTab} />
      {tab === "pl" && <ProfitLoss range={params} />}
      {tab === "stock" && <StockValuation />}
      {tab === "sales" && <Sales range={params} />}
      {tab === "expenses" && <Expenses range={params} />}
      {tab === "accounts" && <AccountSummary range={params} />}
    </div>
  );
}
