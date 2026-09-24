import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { openPrintable } from "../../api/client";
import { useApi } from "../../api/hooks";
import DataTable from "../../components/DataTable";
import { Badge, Button, Card, ErrorBox, Input, NumInput, PageHead, Select } from "../../components/ui";
import { useDebounce, useLocalState, usePermissions } from "../../hooks";
import { date, pasa, pkr, wt } from "../../utils/format";

export const METALS = ["gold", "silver", "palladium"];
export const STATUSES = ["in_stock", "sold", "sr_refine", "returned", "transferred"];

export default function StockPage() {
  const nav = useNavigate();
  const perms = usePermissions();
  const [sp] = useSearchParams();
  const searchRef = useRef(null);
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useLocalState("alnoor.stock.filters", { metal: "", category: "", status: "in_stock" });
  const [more, setMore] = useState({ supplier: "", min_weight: "", max_weight: "", date_from: "", date_to: "" });
  const [page, setPage] = useState(1);
  const [ordering, setOrdering] = useState("");
  const [selected, setSelected] = useState(new Set());
  const q = useDebounce(search, 250);

  useEffect(() => {
    if (sp.get("focus")) searchRef.current?.focus();
  }, [sp]);
  useEffect(() => setPage(1), [q, filters, more]);

  const params = { search: q, ...filters, ...more, page, ordering };
  const { data, isFetching, error } = useApi("/stock/", params);
  const { data: totals } = useApi("/stock/totals/", { search: q, ...filters, ...more });
  const { data: cats } = useApi("/stock/categories/");
  const { data: suppliers } = useApi("/suppliers/", { page_size: 500 });
  const setF = (k) => (e) => setFilters({ ...filters, [k]: e.target.value });
  const setM = (k) => (e) => setMore({ ...more, [k]: e.target.value });

  const columns = [
    { key: "code", label: "Code", sort: "code", render: (r) => <span className="mono strong">{r.code}</span> },
    { key: "category", label: "Category", sort: "category", render: (r) => <>{r.category}{r.metal !== "gold" && <span className="muted small"> · {r.metal}</span>}</> },
    { key: "name", label: "Name / design", className: "hide-mobile", render: (r) => [r.name, r.design].filter(Boolean).join(" · ") || "—" },
    { key: "gross_weight", label: "Gross", num: true, sort: "gross_weight", render: (r) => wt(r.gross_weight) },
    { key: "ratti_kaat", label: "Ratti", num: true, className: "hide-mobile" },
    { key: "pasa", label: "Pasa", num: true, sort: "pasa", render: (r) => pasa(r.pasa) },
    perms.view_profit && { key: "total_cost", label: "Cost", num: true, sort: "total_cost", className: "hide-mobile", render: (r) => pkr(r.total_cost) },
    { key: "value_at_today", label: "Value @ today", num: true, render: (r) => pkr(r.value_at_today) },
    { key: "supplier_name", label: "Supplier", className: "hide-mobile" },
    { key: "purchase_date", label: "Purchased", sort: "purchase_date", className: "hide-mobile", render: (r) => date(r.purchase_date) },
    { key: "status", label: "Status", render: (r) => <Badge>{r.status}</Badge> },
  ].filter(Boolean);

  return (
    <div className="stack">
      <PageHead title="Stock" subtitle="Search by code, name, design or category. Scanning a tag jumps to the item.">
        {selected.size > 0 && (
          <Button onClick={() => openPrintable("/stock/tags/", { ids: [...selected].join(",") })}>
            Print {selected.size} tag(s)
          </Button>
        )}
        <Link className="btn primary" to="/stock/new">Add item</Link>
      </PageHead>

      <Card>
        <div className="form-grid">
          <Input label="Search" className="span-2" value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder="R0111, ring, design…" ref={searchRef} autoFocus={!!sp.get("focus")}
            onKeyDown={(e) => {
              if (e.key === "Enter" && data?.results?.length === 1) nav(`/stock/${data.results[0].id}`);
            }} />
          <Select label="Metal" value={filters.metal} onChange={setF("metal")} options={METALS} placeholder="All" />
          <Select label="Category" value={filters.category} onChange={setF("category")} placeholder="All"
            options={(cats || []).map((c) => ({ value: c.category, label: `${c.category} (${c.count})` }))} />
          <Select label="Status" value={filters.status} onChange={setF("status")} options={STATUSES} placeholder="All" />
          <Select label="Supplier" value={more.supplier} onChange={setM("supplier")} placeholder="All"
            options={(suppliers?.results || []).map((s) => ({ value: s.id, label: s.name }))} />
          <NumInput label="Min gross (g)" value={more.min_weight} onChange={setM("min_weight")} />
          <NumInput label="Max gross (g)" value={more.max_weight} onChange={setM("max_weight")} />
          <Input type="date" label="Purchased from" value={more.date_from} onChange={setM("date_from")} />
          <Input type="date" label="Purchased to" value={more.date_to} onChange={setM("date_to")} />
        </div>
      </Card>

      {totals && (
        <div className="gap small">
          <span className="badge">{totals.items} items</span>
          <span className="badge">{totals.pieces} pcs</span>
          <span className="badge">Gross {wt(totals.gross_weight)} g</span>
          <span className="badge">Gold {wt(totals.gold_weight)} g</span>
          <span className="badge">Pasa {pasa(totals.pasa)}</span>
          {totals.total_cost !== undefined && <span className="badge accent">Cost Rs {pkr(totals.total_cost)}</span>}
          {totals.value_at_today && <span className="badge accent">Gold @ today Rs {pkr(totals.value_at_today)}</span>}
        </div>
      )}

      <ErrorBox error={error} />
      <Card bodyClass="">
        <DataTable columns={columns} data={data} loading={isFetching} onRowClick={(r) => nav(`/stock/${r.id}`)}
          page={page} setPage={setPage} ordering={ordering} setOrdering={setOrdering}
          selectable selected={selected} setSelected={setSelected} empty="No items match these filters." />
      </Card>
    </div>
  );
}
