import { useState } from "react";
import { api, fieldErrors } from "../../api/client";
import { useApi, useInvalidate } from "../../api/hooks";
import { Badge, Button, Card, ErrorBox, Input, Loading, Modal, PageHead, Select, useForm, useToast } from "../../components/ui";
import { usePermissions } from "../../hooks";

function HeadForm({ initial, heads, onClose, onSaved }) {
  const toast = useToast();
  const f = useForm(initial?.id ? { ...initial, parent: initial.parent || "" } : { name: "", type: initial?.type || "E", parent: initial?.parent || "", report_group: "", is_private: false, is_active: true });
  const save = async () => {
    try {
      const body = { ...f.values, parent: f.values.parent || null };
      if (initial?.id) await api.patch(`/heads-of-account/${initial.id}/`, body);
      else await api.post("/heads-of-account/", body);
      toast.ok("Saved");
      onSaved();
    } catch (e) { f.setErrors(fieldErrors(e)); toast.error(e); }
  };
  const parents = heads.filter((h) => !h.parent && h.id !== initial?.id);
  return (
    <Modal title={initial?.id ? "Edit head" : "New head of account"} onClose={onClose}
      footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" onClick={save}>Save</Button></>}>
      <div className="form-grid">
        <Input label="Name" {...f.bind("name")} autoFocus />
        <Select label="Type" {...f.bind("type")} options={[{ value: "I", label: "Income" }, { value: "E", label: "Expenditure" }]} />
        <Select label="Parent (for sub-head)" {...f.bind("parent")} placeholder="— main head —" options={parents.map((p) => ({ value: p.id, label: `${p.name} (${p.type})` }))} />
        <Input label="Report group" {...f.bind("report_group")} placeholder="shop_expenses, home, zakat…" />
        <label className="check"><input type="checkbox" {...f.bind("is_private", "checkbox")} checked={!!f.values.is_private} /> Private (hidden from salespeople)</label>
        <label className="check"><input type="checkbox" {...f.bind("is_active", "checkbox")} checked={!!f.values.is_active} /> Active</label>
      </div>
    </Modal>
  );
}

export default function HeadsPage() {
  const perms = usePermissions();
  const invalidate = useInvalidate();
  const [editing, setEditing] = useState(null);
  const { data, isLoading, error } = useApi("/heads-of-account/");
  if (isLoading) return <Loading />;
  const heads = data || [];
  const tops = heads.filter((h) => !h.parent);
  const canEdit = perms.day_close;

  const Group = ({ type, title }) => (
    <Card title={title} bodyClass="">
      <table className="table"><tbody>
        {tops.filter((h) => h.type === type).map((h) => (
          <FragmentRows key={h.id} head={h} subs={heads.filter((s) => s.parent === h.id)} canEdit={canEdit} onEdit={setEditing} />
        ))}
      </tbody></table>
    </Card>
  );

  return (
    <div className="stack">
      <PageHead title="Heads of account" subtitle="Income & expenditure heads used by the cash book and reports.">
        {canEdit && <Button variant="primary" onClick={() => setEditing({})}>Add head</Button>}
      </PageHead>
      <ErrorBox error={error} />
      <div className="grid grid-2">
        <Group type="I" title="Income" />
        <Group type="E" title="Expenditure" />
      </div>
      {editing && <HeadForm initial={editing} heads={heads} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); invalidate("/heads-of-account"); }} />}
    </div>
  );
}

function FragmentRows({ head, subs, canEdit, onEdit }) {
  const row = (h, sub) => (
    <tr key={h.id} style={{ opacity: h.is_active ? 1 : 0.5 }}>
      <td style={{ paddingLeft: sub ? 28 : 10 }} className={sub ? "" : "strong"}>{sub ? "› " : ""}{h.name}</td>
      <td>{h.report_group && <Badge>{h.report_group}</Badge>} {h.is_private && <Badge kind="warn">private</Badge>} {!h.is_active && <Badge kind="danger">inactive</Badge>}</td>
      <td className="right nowrap">
        {canEdit && !sub && <Button size="sm" variant="ghost" onClick={() => onEdit({ parent: h.id, type: h.type })}>+ Sub</Button>}
        {canEdit && <Button size="sm" variant="ghost" onClick={() => onEdit(h)}>Edit</Button>}
      </td>
    </tr>
  );
  return <>{row(head, false)}{subs.map((s) => row(s, true))}</>;
}
