import { useState } from "react";
import { useApi } from "../../api/hooks";
import { Card, ErrorBox, Input, PageHead, Select, Stat } from "../../components/ui";
import { date, pkr, todayISO } from "../../utils/format";

export default function ZakatPage() {
  const [p, setP] = useState({ date: todayISO(), basis: "sell", deduct_liabilities: "1" });
  const { data: z, error, isFetching } = useApi("/zakat/calculate/", p);
  return (
    <div className="stack">
      <PageHead title="Zakat" subtitle="Stock + cash + receivables (− liabilities) × zakat rate. Method pending owner confirmation." />
      <Card>
        <div className="form-grid">
          <Input type="date" label="Zakat date" value={p.date} onChange={(e) => setP({ ...p, date: e.target.value })} />
          <Select label="Value gold at" value={p.basis} onChange={(e) => setP({ ...p, basis: e.target.value })}
            options={[{ value: "sell", label: "Selling rate" }, { value: "buy", label: "Buying rate" }, { value: "cost", label: "Purchase cost" }]} />
          <Select label="Supplier payables" value={p.deduct_liabilities} onChange={(e) => setP({ ...p, deduct_liabilities: e.target.value })}
            options={[{ value: "1", label: "Deduct" }, { value: "0", label: "Do not deduct" }]} />
        </div>
      </Card>
      <ErrorBox error={error} />
      {z && (
        <div style={{ opacity: isFetching ? 0.6 : 1 }} className="stack">
          <div className="grid grid-4">
            <Stat label="Stock" value={pkr(z.stock_value)} hint={`${z.stock_items} items @ ${pkr(z.rate_per_tola)}/tola (${date(z.rate_date)})`} />
            <Stat label="Old gold on hand" value={pkr(z.old_gold_value)} />
            <Stat label="Cash (all accounts)" value={pkr(z.cash)} />
            <Stat label="Receivables" value={pkr(z.receivables)} />
            <Stat label="Liabilities" value={`− ${pkr(z.liabilities)}`} />
            <Stat label="Zakatable total" value={pkr(z.zakatable_total)} />
            <Stat label={`Zakat due (${z.zakat_rate_percent}%)`} value={`Rs ${pkr(z.zakat_due)}`} />
          </div>
          <p className="small muted">{z.note}</p>
        </div>
      )}
    </div>
  );
}
