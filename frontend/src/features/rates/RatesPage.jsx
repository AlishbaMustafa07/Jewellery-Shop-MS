import { useState } from "react";
import { api } from "../../api/client";
import { useApi, useInvalidate } from "../../api/hooks";
import DataTable from "../../components/DataTable";
import { Alert, Button, Card, Input, NumInput, PageHead, Stat, useToast } from "../../components/ui";
import { useGoldRate, usePermissions } from "../../hooks";
import { date, dateTime, pkr, todayISO } from "../../utils/format";

export default function RatesPage() {
  const perms = usePermissions();
  const toast = useToast();
  const invalidate = useInvalidate();
  const { rate, isToday } = useGoldRate();
  const [v, setV] = useState({ date: todayISO(), buy_rate_per_tola: "", sell_rate_per_tola: "" });
  const [page, setPage] = useState(1);
  const { data, isFetching } = useApi("/gold-rates/", { page });

  const save = async () => {
    try {
      await api.post("/gold-rates/", v);
      toast.ok("Gold rate saved");
      invalidate("/gold-rates", "/dashboard", "/stock");
      setV({ ...v, buy_rate_per_tola: "", sell_rate_per_tola: "" });
    } catch (e) { toast.error(e); }
  };
  const perGram = (r) => (r ? pkr(Number(r) / 11.664) : "—");

  return (
    <div className="stack">
      <PageHead title="Gold rate" subtitle="PKR per tola (11.664 g). Past rates are never overwritten; every sale stores the rate it used." />
      <div className="grid grid-4">
        <Stat label="Sell / tola" value={rate ? pkr(rate.sell_rate_per_tola) : "—"} hint={rate ? `${perGram(rate.sell_rate_per_tola)} / g` : ""} />
        <Stat label="Buy / tola" value={rate ? pkr(rate.buy_rate_per_tola) : "—"} hint={rate ? `${perGram(rate.buy_rate_per_tola)} / g` : ""} />
        <Stat label="Rate date" value={rate ? date(rate.date) : "—"} hint={isToday ? "Today" : "Not today"} />
      </div>
      {perms.set_gold_rate ? (
        <Card title={isToday ? "Correct today's rate" : "Set today's rate"}>
          <div className="form-grid">
            <Input type="date" label="Date" value={v.date} max={todayISO()} onChange={(e) => setV({ ...v, date: e.target.value })} />
            <NumInput label="Buy rate / tola" value={v.buy_rate_per_tola} onChange={(e) => setV({ ...v, buy_rate_per_tola: e.target.value })} autoFocus />
            <NumInput label="Sell rate / tola" value={v.sell_rate_per_tola} onChange={(e) => setV({ ...v, sell_rate_per_tola: e.target.value })} />
          </div>
          <div className="gap" style={{ marginTop: 12 }}>
            <Button variant="primary" disabled={!v.buy_rate_per_tola || !v.sell_rate_per_tola} onClick={save}>Save rate</Button>
            <span className="small muted">A missing past date can be back-filled once; existing past rates are locked.</span>
          </div>
        </Card>
      ) : (
        !isToday && <Alert kind="warn">Today's rate is not set yet. Ask the owner or a manager to enter it.</Alert>
      )}
      <Card title="History" bodyClass="">
        <DataTable data={data} loading={isFetching} page={page} setPage={setPage} columns={[
          { key: "date", label: "Date", render: (r) => date(r.date) },
          { key: "buy_rate_per_tola", label: "Buy / tola", num: true, render: (r) => pkr(r.buy_rate_per_tola) },
          { key: "sell_rate_per_tola", label: "Sell / tola", num: true, render: (r) => pkr(r.sell_rate_per_tola) },
          { key: "g", label: "Sell / g", num: true, className: "hide-mobile", render: (r) => perGram(r.sell_rate_per_tola) },
          { key: "entered_by_name", label: "Entered by", className: "hide-mobile" },
          { key: "created_at", label: "At", className: "hide-mobile", render: (r) => dateTime(r.created_at) },
        ]} />
      </Card>
    </div>
  );
}
