import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, openPrintable } from "../../api/client";
import { useApi, useInvalidate } from "../../api/hooks";
import { Badge, Button, Card, ConfirmReason, ErrorBox, Loading, PageHead, useToast } from "../../components/ui";
import { usePermissions } from "../../hooks";
import { date, label, pasa, pkr, wt } from "../../utils/format";

function Row({ k, v }) {
  return (
    <tr><td className="muted" style={{ width: "45%" }}>{k}</td><td className="strong">{v ?? "—"}</td></tr>
  );
}

export default function StockDetailPage() {
  const { id } = useParams();
  const perms = usePermissions();
  const toast = useToast();
  const invalidate = useInvalidate();
  const { data: it, isLoading, error, refetch } = useApi(`/stock/${id}/`);
  const [returning, setReturning] = useState(false);
  const [busy, setBusy] = useState(false);
  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;

  const upload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("photo", file);
    try {
      await api.post(`/stock/${id}/photo/`, fd);
      toast.ok("Photo uploaded");
      refetch();
    } catch (err) {
      toast.error(err);
    }
  };
  const act = async (fn, msg) => {
    setBusy(true);
    try {
      await fn();
      toast.ok(msg);
      invalidate("/stock", "/suppliers");
      refetch();
    } catch (err) {
      toast.error(err);
    } finally {
      setBusy(false);
    }
  };
  const canManage = perms.view_profit;

  return (
    <div className="stack">
      <PageHead title={<span className="mono">{it.code}</span>} subtitle={`${it.category} · ${label(it.metal)}`}>
        <Badge>{it.status}</Badge>
        <Button onClick={() => openPrintable(`/stock/${id}/tag/`)}>Print tag</Button>
        {it.status === "in_stock" && <Link className="btn primary" to={`/sales/new?item=${it.code}`}>Sell</Link>}
        <Link className="btn" to={`/stock/${id}/edit`}>Edit</Link>
      </PageHead>
      <div className="grid grid-2">
        <Card title="Details" bodyClass="">
          <table className="table"><tbody>
            <Row k="Name" v={it.name} />
            <Row k="Design / size" v={[it.design, it.size].filter(Boolean).join(" · ") || "—"} />
            <Row k="Pieces / type" v={`${it.pieces} · ${label(it.type)}`} />
            <Row k="Nature / source" v={`${label(it.nature)} · ${label(it.source_type)}`} />
            <Row k="Supplier" v={it.supplier ? <Link to={`/suppliers/${it.supplier}`}>{it.supplier_name}</Link> : "—"} />
            <Row k="Book / page" v={[it.book_no, it.page_no].filter(Boolean).join(" / ") || "—"} />
            <Row k="Purchase date" v={date(it.purchase_date)} />
            {it.sold_date && <Row k="Sold on" v={date(it.sold_date)} />}
            {it.notes && <Row k="Notes" v={it.notes} />}
          </tbody></table>
        </Card>
        <Card title="Weight & value" bodyClass="">
          <table className="table"><tbody>
            <Row k="Gross weight" v={`${wt(it.gross_weight)} g`} />
            <Row k="Big stone" v={`${wt(it.big_stone_weight)} g`} />
            <Row k="Palladium / diamond" v={`${wt(it.pd_diamond_weight)} g`} />
            <Row k="Extra / less gold" v={`${wt(it.extra_less_gold)} g`} />
            <Row k="Gold weight" v={`${wt(it.gold_weight)} g`} />
            <Row k="Ratti kaat" v={it.ratti_kaat} />
            <Row k="Pasa" v={pasa(it.pasa)} />
            {canManage && <Row k="Purchase rate / tola" v={pkr(it.purchase_rate)} />}
            {canManage && <Row k="Gold price" v={`Rs ${pkr(it.gold_price)}`} />}
            {canManage && <Row k="Extra costs" v={`Rs ${pkr(it.extra_costs)}`} />}
            {canManage && <Row k="Total cost" v={`Rs ${pkr(it.total_cost)}`} />}
            <Row k="Gold value at today's rate" v={it.value_at_today ? `Rs ${pkr(it.value_at_today)}` : "—"} />
          </tbody></table>
        </Card>
      </div>
      <Card title="Photo" actions={<label className="btn sm">Upload<input type="file" accept="image/*" hidden onChange={upload} /></label>}>
        {it.photo_url ? <img src={it.photo_url} alt={it.code} style={{ maxWidth: "100%", maxHeight: 360, borderRadius: 8 }} /> : <div className="muted">No photo.</div>}
      </Card>
      {canManage && it.status !== "sold" && (
        <Card title="Stock actions">
          <div className="gap">
            {it.status === "in_stock" && it.supplier && <Button variant="danger" disabled={busy} onClick={() => setReturning(true)}>Return to supplier</Button>}
            {it.status === "in_stock" && <Button disabled={busy} onClick={() => act(() => api.post(`/stock/${id}/set-status/`, { status: "transferred" }), "Marked transferred")}>Mark transferred</Button>}
            {it.status === "transferred" && <Button disabled={busy} onClick={() => act(() => api.post(`/stock/${id}/set-status/`, { status: "in_stock" }), "Back in stock")}>Back in stock</Button>}
            {it.status === "sr_refine" && <span className="muted">This item is in a refine lot — manage it under Old gold & refine.</span>}
          </div>
        </Card>
      )}
      {returning && (
        <ConfirmReason title={`Return ${it.code} to ${it.supplier_name}`} prompt="The supplier's balance will be reduced by the item cost."
          confirmLabel="Return item" busy={busy} onClose={() => setReturning(false)}
          onConfirm={(notes) => act(() => api.post(`/stock/${id}/return-to-supplier/`, { notes }), "Returned").then(() => setReturning(false))} />
      )}
    </div>
  );
}
