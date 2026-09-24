import { useState } from "react";
import { api } from "../../api/client";
import { useApi, useInvalidate } from "../../api/hooks";
import DataTable from "../../components/DataTable";
import { Badge, Button, Card, Input, Modal, NumInput, PageHead, Select, Stat, Tabs, useToast } from "../../components/ui";
import { useSettings } from "../../hooks";
import { date, pasa, pkr, todayISO, wt } from "../../utils/format";

function NewLot({ onClose, onDone }) {
  const toast = useToast();
  const [refiner, setRefiner] = useState("MH Lab");
  const [day, setDay] = useState(todayISO());
  const [notes, setNotes] = useState("");
  const [og, setOg] = useState(new Set());
  const [items, setItems] = useState(new Set());
  const { data: pending } = useApi("/old-gold/", { status: "pending", page_size: 500 });
  const { data: oldStock } = useApi("/stock/", { status: "in_stock", nature: "old", page_size: 500 });
  const save = async () => {
    try {
      await api.post("/refine-lots/", { refiner, date: day, notes, old_gold: [...og], stock_items: [...items] });
      toast.ok("Refine lot created");
      onDone();
    } catch (e) { toast.error(e); }
  };
  return (
    <Modal wide title="Send gold to refine" onClose={onClose}
      footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" disabled={!og.size && !items.size} onClick={save}>Create lot ({og.size + items.size})</Button></>}>
      <div className="form-grid">
        <Input label="Refiner" value={refiner} onChange={(e) => setRefiner(e.target.value)} />
        <Input type="date" label="Date" value={day} onChange={(e) => setDay(e.target.value)} />
        <Input label="Notes" className="span-2" value={notes} onChange={(e) => setNotes(e.target.value)} />
      </div>
      <h3 style={{ marginTop: 16 }}>Pending old gold</h3>
      <DataTable data={pending} selectable selected={og} setSelected={setOg} empty="No pending old gold." columns={[
        { key: "date", label: "Date", render: (r) => date(r.date) },
        { key: "invoice_number", label: "Invoice", className: "mono" },
        { key: "customer_name", label: "Customer" },
        { key: "weight", label: "Weight", num: true, render: (r) => wt(r.weight) },
        { key: "ratti_kaat", label: "Ratti", num: true },
        { key: "pasa", label: "Pasa", num: true, render: (r) => pasa(r.pasa) },
      ]} />
      <h3 style={{ marginTop: 16 }}>Old-nature stock items</h3>
      <DataTable data={oldStock} selectable selected={items} setSelected={setItems} empty="No in-stock items marked 'old'." columns={[
        { key: "code", label: "Code", className: "mono" },
        { key: "category", label: "Category" },
        { key: "gold_weight", label: "Gold wt", num: true, render: (r) => wt(r.gold_weight) },
        { key: "pasa", label: "Pasa", num: true, render: (r) => pasa(r.pasa) },
      ]} />
    </Modal>
  );
}

function ReturnLot({ lot, onClose, onDone }) {
  const toast = useToast();
  const { data: settings } = useSettings();
  const [v, setV] = useState({ pasa_returned: lot.pasa_returned || "", returned_date: todayISO(), cost: lot.cost || "", cost_cash_account: "shop_cash", notes: lot.notes });
  const save = async () => {
    try {
      await api.patch(`/refine-lots/${lot.id}/`, { ...v, pasa_returned: v.pasa_returned === "" ? null : v.pasa_returned, cost: v.cost || "0" });
      toast.ok("Lot updated");
      onDone();
    } catch (e) { toast.error(e); }
  };
  return (
    <Modal title={`Refine lot — ${lot.refiner} ${date(lot.date)}`} onClose={onClose}
      footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" onClick={save}>Save</Button></>}>
      <p className="muted">Sent {wt(lot.weight_sent)} g · expected pasa {pasa(lot.expected_pasa)}</p>
      <div className="form-grid">
        <NumInput label="Pasa returned (fine gold g)" value={v.pasa_returned} onChange={(e) => setV({ ...v, pasa_returned: e.target.value })} autoFocus />
        <Input type="date" label="Returned on" value={v.returned_date} onChange={(e) => setV({ ...v, returned_date: e.target.value })} />
        <NumInput label="Refining cost (Rs)" value={v.cost} onChange={(e) => setV({ ...v, cost: e.target.value })} hint="Posted to cash book under Refine" />
        <Select label="Paid from" value={v.cost_cash_account} onChange={(e) => setV({ ...v, cost_cash_account: e.target.value })} options={settings?.cash_accounts || ["shop_cash"]} />
        <Input label="Notes" className="span-2" value={v.notes} onChange={(e) => setV({ ...v, notes: e.target.value })} />
      </div>
    </Modal>
  );
}

export default function RefiningPage() {
  const invalidate = useInvalidate();
  const [tab, setTab] = useState("lots");
  const [creating, setCreating] = useState(false);
  const [open, setOpen] = useState(null);
  const [page, setPage] = useState(1);
  const { data: bal } = useApi("/refine/balance/");
  const { data: lots, isFetching } = useApi("/refine-lots/", { page });
  const { data: og, isFetching: ogf } = useApi(tab === "old" ? "/old-gold/" : null, { page_size: 200 });
  const done = () => { setCreating(false); setOpen(null); invalidate("/refine", "/old-gold", "/stock", "/cash-book"); };

  return (
    <div className="stack">
      <PageHead title="Old gold & refining"><Button variant="primary" onClick={() => setCreating(true)}>Send to refine</Button></PageHead>
      {bal && (
        <div className="grid grid-4">
          <Stat label="Pending old gold" value={`${pasa(bal.pending_old_gold.pasa)} pasa`} hint={`${bal.pending_old_gold.count} pcs · ${wt(bal.pending_old_gold.weight)} g · credited ${pkr(bal.pending_old_gold.credited_value)}`} />
          <Stat label="At refiner" value={`${pasa(bal.at_refiner.pasa)} pasa`} hint={`${wt(bal.at_refiner.weight)} g sent`} />
          <Stat label="Fine gold returned" value={`${pasa(bal.refined.pasa_returned)} g`} hint={`loss ${pasa(bal.refined.loss_pasa)} · cost ${pkr(bal.refined.total_cost)}`} />
          <Stat label="Refine pool" value={`${pasa(bal.pool_pasa)} pasa`} hint={bal.rate_used ? `@ buy ${pkr(bal.rate_used)}` : ""} />
        </div>
      )}
      <Tabs value={tab} onChange={setTab} tabs={[{ value: "lots", label: "Refine lots" }, { value: "old", label: "Old gold received" }]} />
      {tab === "lots" ? (
        <Card bodyClass="">
          <DataTable data={lots} loading={isFetching} page={page} setPage={setPage} onRowClick={setOpen} columns={[
            { key: "date", label: "Sent", render: (r) => date(r.date) },
            { key: "refiner", label: "Refiner" },
            { key: "items", label: "Pieces", num: true, render: (r) => r.items.length },
            { key: "weight_sent", label: "Weight", num: true, render: (r) => wt(r.weight_sent) },
            { key: "expected_pasa", label: "Expected pasa", num: true, render: (r) => pasa(r.expected_pasa) },
            { key: "pasa_returned", label: "Returned", num: true, render: (r) => (r.pasa_returned ? pasa(r.pasa_returned) : "—") },
            { key: "loss_pasa", label: "Loss", num: true, render: (r) => (r.loss_pasa ? pasa(r.loss_pasa) : "—") },
            { key: "cost", label: "Cost", num: true, render: (r) => pkr(r.cost) },
            { key: "status", label: "Status", render: (r) => <Badge>{r.status}</Badge> },
          ]} />
        </Card>
      ) : (
        <Card bodyClass="">
          <DataTable data={og} loading={ogf} columns={[
            { key: "date", label: "Date", render: (r) => date(r.date) },
            { key: "invoice_number", label: "Invoice", className: "mono" },
            { key: "customer_name", label: "Customer" },
            { key: "description", label: "Description", className: "hide-mobile" },
            { key: "weight", label: "Weight", num: true, render: (r) => wt(r.weight) },
            { key: "ratti_kaat", label: "Ratti", num: true },
            { key: "pasa", label: "Pasa", num: true, render: (r) => pasa(r.pasa) },
            { key: "value", label: "Credited", num: true, render: (r) => pkr(r.value) },
            { key: "status", label: "Status", render: (r) => <Badge>{r.status}</Badge> },
          ]} />
        </Card>
      )}
      {creating && <NewLot onClose={() => setCreating(false)} onDone={done} />}
      {open && <ReturnLot lot={open} onClose={() => setOpen(null)} onDone={done} />}
    </div>
  );
}
