import { useEffect, useState } from "react";
import { useApi } from "../../api/hooks";
import DataTable from "../../components/DataTable";
import { Badge, Card, Input, Modal, PageHead, Select } from "../../components/ui";
import { useDebounce } from "../../hooks";
import { dateTime, label } from "../../utils/format";

const ACTIONS = ["create", "update", "delete", "void", "login", "lock", "unlock", "other"];

export default function AuditLogPage() {
  const [search, setSearch] = useState("");
  const [f, setF] = useState({ action: "", entity_type: "", user: "", date_from: "", date_to: "" });
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(null);
  const q = useDebounce(search);
  useEffect(() => setPage(1), [q, f]);
  const { data, isFetching } = useApi("/audit-log/", { search: q, ...f, page });
  const { data: users } = useApi("/users/");
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  return (
    <div className="stack">
      <PageHead title="Audit log" subtitle="Every change: who, when, old and new values. Entries cannot be edited or deleted." />
      <Card>
        <div className="form-grid">
          <Input label="Search" className="span-2" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Record, note, id…" />
          <Select label="Action" value={f.action} onChange={set("action")} options={ACTIONS} placeholder="All" />
          <Input label="Entity type" value={f.entity_type} onChange={set("entity_type")} placeholder="sales.invoice" />
          <Select label="User" value={f.user} onChange={set("user")} placeholder="All" options={(users?.results || []).map((u) => ({ value: u.id, label: u.username }))} />
          <Input type="date" label="From" value={f.date_from} onChange={set("date_from")} />
          <Input type="date" label="To" value={f.date_to} onChange={set("date_to")} />
        </div>
      </Card>
      <Card bodyClass="">
        <DataTable data={data} loading={isFetching} page={page} setPage={setPage} onRowClick={setOpen} columns={[
          { key: "created_at", label: "When", render: (r) => dateTime(r.created_at) },
          { key: "user_name", label: "User" },
          { key: "action", label: "Action", render: (r) => <Badge kind={r.action === "void" || r.action === "delete" ? "danger" : r.action === "create" ? "ok" : "info"}>{r.action}</Badge> },
          { key: "entity_type", label: "Type", render: (r) => label(r.entity_type.split(".")[1]) },
          { key: "entity_repr", label: "Record" },
          { key: "note", label: "Note", className: "hide-mobile" },
        ]} />
      </Card>
      {open && (
        <Modal wide title={`${label(open.action)} · ${open.entity_repr}`} onClose={() => setOpen(null)}>
          <p className="muted small">{dateTime(open.created_at)} by {open.user_name || "system"} · {open.entity_type} {open.entity_id}</p>
          {open.note && <p>{open.note}</p>}
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Field</th><th>Old</th><th>New</th></tr></thead>
              <tbody>
                {Object.entries(open.changes.new && !open.changes.old ? Object.fromEntries(Object.entries(open.changes.new).map(([k, v]) => [k, { new: v }]))
                  : open.changes.old && !open.changes.new ? Object.fromEntries(Object.entries(open.changes.old).map(([k, v]) => [k, { old: v }]))
                    : open.changes).map(([k, v]) => (
                  <tr key={k}><td className="mono small">{k}</td><td className="small">{typeof v === "object" && v !== null ? String(v.old ?? "") : ""}</td><td className="small">{typeof v === "object" && v !== null ? String(v.new ?? "") : String(v)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </Modal>
      )}
    </div>
  );
}
