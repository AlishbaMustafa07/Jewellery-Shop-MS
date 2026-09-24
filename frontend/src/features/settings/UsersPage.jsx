import { useState } from "react";
import { api, fieldErrors } from "../../api/client";
import { useApi, useInvalidate } from "../../api/hooks";
import DataTable from "../../components/DataTable";
import { Badge, Button, Card, Input, Modal, NumInput, PageHead, Select, useForm, useToast } from "../../components/ui";
import { dateTime, label, pkr } from "../../utils/format";

const ROLES = ["owner", "manager", "accountant", "salesperson"];

function UserForm({ initial, onClose, onSaved }) {
  const toast = useToast();
  const f = useForm(initial?.id ? { ...initial, password: "", discount_limit: initial.discount_limit ?? "" } : { username: "", first_name: "", last_name: "", phone: "", role: "salesperson", password: "", discount_limit: "", is_active: true });
  const save = async () => {
    const body = { username: f.values.username, first_name: f.values.first_name, last_name: f.values.last_name, phone: f.values.phone,
      role: f.values.role, is_active: f.values.is_active, discount_limit: f.values.discount_limit === "" ? null : f.values.discount_limit };
    if (f.values.password) body.password = f.values.password;
    try {
      if (initial?.id) await api.patch(`/users/${initial.id}/`, body);
      else await api.post("/users/", body);
      toast.ok("User saved");
      onSaved();
    } catch (e) { f.setErrors(fieldErrors(e)); toast.error(e); }
  };
  return (
    <Modal title={initial?.id ? `Edit ${initial.username}` : "New user"} onClose={onClose}
      footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" onClick={save}>Save</Button></>}>
      <div className="form-grid">
        <Input label="Username" {...f.bind("username")} autoFocus />
        <Select label="Role" {...f.bind("role")} options={ROLES} />
        <Input label="First name" {...f.bind("first_name")} />
        <Input label="Last name" {...f.bind("last_name")} />
        <Input label="Phone" {...f.bind("phone")} />
        <NumInput label="Discount limit (Rs)" {...f.bind("discount_limit")} hint="Blank = role default" />
        <Input type="password" label={initial?.id ? "New password (optional)" : "Password"} {...f.bind("password")} autoComplete="new-password" />
        <label className="check"><input type="checkbox" checked={!!f.values.is_active} onChange={(e) => f.set("is_active", e.target.checked)} /> Active</label>
      </div>
    </Modal>
  );
}

export default function UsersPage() {
  const invalidate = useInvalidate();
  const [editing, setEditing] = useState(null);
  const { data, isFetching } = useApi("/users/");
  return (
    <div className="stack">
      <PageHead title="Users" subtitle="Each person gets their own login. Deactivate instead of deleting so history stays intact.">
        <Button variant="primary" onClick={() => setEditing({})}>Add user</Button>
      </PageHead>
      <Card bodyClass="">
        <DataTable data={data} loading={isFetching} onRowClick={setEditing} columns={[
          { key: "username", label: "Username", render: (r) => <span className="strong">{r.username}</span> },
          { key: "full_name", label: "Name" },
          { key: "role", label: "Role", render: (r) => <Badge kind="accent">{label(r.role)}</Badge> },
          { key: "discount_limit", label: "Discount limit", num: true, render: (r) => (r.discount_limit ? pkr(r.discount_limit) : "default") },
          { key: "last_login", label: "Last login", className: "hide-mobile", render: (r) => dateTime(r.last_login) },
          { key: "is_active", label: "Status", render: (r) => (r.is_active ? <Badge kind="ok">active</Badge> : <Badge kind="danger">inactive</Badge>) },
        ]} />
      </Card>
      {editing && <UserForm initial={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); invalidate("/users"); }} />}
    </div>
  );
}
