import { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, fieldErrors } from "../../api/client";
import { useApi, useInvalidate } from "../../api/hooks";
import { SupplierPicker } from "../../components/Pickers";
import { Button, Card, ErrorBox, Input, Loading, NumInput, PageHead, Select, TextArea, useForm, useToast } from "../../components/ui";
import { useGoldRate, usePermissions, useRole, useSettings } from "../../hooks";
import { stockCost } from "../../utils/calculations";
import { pasa, pkr, todayISO, wt } from "../../utils/format";
import { METALS } from "./StockPage";

const EMPTY = {
  code: "", metal: "gold", category: "", name: "", pieces: 1, type: "plain", size: "", design: "", supplier: null,
  nature: "new", source_type: "current_purchase", book_no: "", page_no: "", gross_weight: "", big_stone_weight: "0",
  pd_diamond_weight: "0", extra_less_gold: "0", ratti_kaat: "90", purchase_rate: "", extra_costs: "0",
  purchase_date: todayISO(), notes: "",
};

export default function StockFormPage() {
  const { id } = useParams();
  const editing = !!id;
  const nav = useNavigate();
  const toast = useToast();
  const invalidate = useInvalidate();
  const perms = usePermissions();
  const role = useRole();
  const { rate } = useGoldRate();
  const { data: settings } = useSettings();
  const { data: existing, isLoading, error } = useApi(editing ? `/stock/${id}/` : null);
  const f = useForm(EMPTY);
  const v = f.values;

  useEffect(() => {
    if (existing) f.setValues({ ...EMPTY, ...existing, supplier: existing.supplier ? { id: existing.supplier, name: existing.supplier_name, type: "" } : null });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [existing]);
  useEffect(() => {
    if (!editing && !v.purchase_rate && rate) f.set("purchase_rate", rate.buy_rate_per_tola);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rate]);

  const { data: nextCode } = useApi(!editing && v.category ? "/stock/next-code/" : null, { category: v.category },
    { retry: false });

  if (editing && isLoading) return <Loading />;
  const calc = stockCost(v);
  const categories = Object.keys(settings?.code_prefixes || {});

  const save = async (andNew) => {
    f.setErrors({});
    const body = { ...v, supplier: v.supplier?.id || null };
    for (const k of ["id", "gold_weight", "pasa", "gold_price", "total_cost", "value_at_today", "photo", "photo_url",
      "status", "supplier_name", "created_at", "updated_at", "sold_date"]) delete body[k];
    if (!body.code) delete body.code;
    if (!perms.view_profit && editing) { delete body.purchase_rate; delete body.extra_costs; }
    try {
      const { data } = editing ? await api.patch(`/stock/${id}/`, body) : await api.post("/stock/", body);
      invalidate("/stock", "/suppliers", "/dashboard");
      toast.ok(`${editing ? "Saved" : "Added"} ${data.code}`);
      if (andNew) {
        f.setValues({ ...EMPTY, category: v.category, metal: v.metal, supplier: v.supplier, purchase_rate: v.purchase_rate,
          ratti_kaat: v.ratti_kaat, purchase_date: v.purchase_date, source_type: v.source_type, nature: v.nature });
      } else nav(`/stock/${data.id}`);
    } catch (e) {
      f.setErrors(fieldErrors(e));
      toast.error(e);
    }
  };

  return (
    <div className="stack">
      <PageHead title={editing ? `Edit ${existing?.code}` : "Add stock item"}
        subtitle="Gold weight, pasa and cost are calculated automatically." />
      <ErrorBox error={error} />
      <form onSubmit={(e) => { e.preventDefault(); save(false); }} className="grid" style={{ gridTemplateColumns: "minmax(0,1fr)" }}>
        <Card title="Item">
          <div className="form-grid">
            <Select label="Metal" {...f.bind("metal")} options={METALS} />
            <Select label="Category" {...f.bind("category")} placeholder="Choose…" required
              options={categories.map((c) => ({ value: c, label: `${c} (${settings.code_prefixes[c]})` }))}
              hint={!categories.length ? "Add categories in Settings" : undefined} />
            <Input label="Code" {...f.bind("code")} disabled={editing ? role !== "owner" : !["owner", "manager"].includes(role)}
              placeholder={nextCode?.code ? `Auto: ${nextCode.code}` : "Auto"} hint={!editing ? "Leave blank to auto-number" : undefined} />
            <Input label="Name / description" className="span-2" {...f.bind("name")} />
            <NumInput label="Pieces" {...f.bind("pieces")} />
            <Select label="Type" {...f.bind("type")} options={["plain", "jurao"]} />
            <Input label="Size (inches)" {...f.bind("size")} />
            <Input label="Design" {...f.bind("design")} />
            <Select label="Nature" {...f.bind("nature")} options={["new", "transfer", "karigar", "old"]} />
            <Select label="Source" {...f.bind("source_type")} options={["current_purchase", "opening_stock"]} />
            <div className="span-2">
              <SupplierPicker label="Supplier / karigar" value={v.supplier} onChange={(s) => f.set("supplier", s)} error={f.errors.supplier} />
            </div>
            <Input type="date" label="Purchase date" {...f.bind("purchase_date")} />
            <Input label="Book no." {...f.bind("book_no")} />
            <Input label="Page no." {...f.bind("page_no")} />
          </div>
        </Card>

        <Card title="Weights & cost">
          <div className="form-grid">
            <NumInput label="Gross wt (g)" {...f.bind("gross_weight")} required />
            <NumInput label="Big stone (g)" {...f.bind("big_stone_weight")} />
            <NumInput label="Palladium / diamond (g)" {...f.bind("pd_diamond_weight")} />
            <NumInput label="Extra / less gold (±g)" {...f.bind("extra_less_gold")} />
            <NumInput label="Ratti kaat (/96)" {...f.bind("ratti_kaat")} required />
            {(perms.view_profit || !editing) && (
              <>
                <NumInput label="Purchase rate / tola" {...f.bind("purchase_rate")} hint="Defaults to today's buy rate" />
                <NumInput label="Extra costs (beads, stones…)" {...f.bind("extra_costs")} />
              </>
            )}
            <TextArea label="Notes" className="span-all" {...f.bind("notes")} />
          </div>
          <div className="gap" style={{ marginTop: 14 }}>
            <span className="badge info">Gold wt {wt(calc.gold_weight)} g</span>
            <span className="badge info">Pasa {pasa(calc.pasa)}</span>
            {perms.view_profit && <span className="badge accent">Gold price Rs {pkr(calc.gold_price)}</span>}
            {perms.view_profit && <span className="badge accent">Total cost Rs {pkr(calc.total_cost)}</span>}
          </div>
        </Card>
        <div className="gap">
          <Button type="submit" variant="primary">Save</Button>
          {!editing && <Button onClick={() => save(true)}>Save & add another</Button>}
          <Button variant="ghost" onClick={() => nav(-1)}>Cancel</Button>
        </div>
      </form>
    </div>
  );
}
