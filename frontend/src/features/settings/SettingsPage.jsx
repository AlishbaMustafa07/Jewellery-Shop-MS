import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fieldErrors } from "../../api/client";
import { useInvalidate } from "../../api/hooks";
import { Button, Card, ErrorBox, Input, Loading, NumInput, PageHead, Select, TextArea, useToast } from "../../components/ui";
import { usePermissions, useSettings } from "../../hooks";

function ChangePassword() {
  const toast = useToast();
  const [v, setV] = useState({ old_password: "", new_password: "", confirm: "" });
  const save = async () => {
    if (v.new_password !== v.confirm) return toast.error("New passwords do not match.");
    try {
      await api.post("/auth/change-password/", v);
      toast.ok("Password changed");
      setV({ old_password: "", new_password: "", confirm: "" });
    } catch (e) { toast.error(e); }
  };
  return (
    <Card title="Change my password">
      <div className="form-grid">
        <Input type="password" label="Current password" value={v.old_password} onChange={(e) => setV({ ...v, old_password: e.target.value })} autoComplete="current-password" />
        <Input type="password" label="New password" value={v.new_password} onChange={(e) => setV({ ...v, new_password: e.target.value })} autoComplete="new-password" hint="At least 8 characters, not all numbers" />
        <Input type="password" label="Repeat new password" value={v.confirm} onChange={(e) => setV({ ...v, confirm: e.target.value })} autoComplete="new-password" />
      </div>
      <Button style={{ marginTop: 12 }} onClick={save} disabled={!v.old_password || !v.new_password}>Change password</Button>
    </Card>
  );
}

export default function SettingsPage() {
  const perms = usePermissions();
  const toast = useToast();
  const invalidate = useInvalidate();
  const { data, isLoading, error } = useSettings();
  const [v, setV] = useState(null);
  const [prefixes, setPrefixes] = useState([]);
  const [accounts, setAccounts] = useState("");
  const [errors, setErrors] = useState({});
  const owner = perms.manage_settings;

  useEffect(() => {
    if (!data) return;
    setV(data);
    setPrefixes(Object.entries(data.code_prefixes || {}).map(([category, prefix]) => ({ category, prefix })));
    setAccounts((data.cash_accounts || []).join(", "));
  }, [data]);

  if (isLoading || !v) return error ? <ErrorBox error={error} /> : <Loading />;

  const save = async () => {
    setErrors({});
    const body = {
      shop_name: v.shop_name, address: v.address, phone: v.phone, receipt_footer_text: v.receipt_footer_text,
      invoice_prefix: v.invoice_prefix, sale_gold_basis: v.sale_gold_basis, zakat_rate_percent: v.zakat_rate_percent,
      default_discount_limit_manager: v.default_discount_limit_manager, default_discount_limit_staff: v.default_discount_limit_staff,
      code_prefixes: Object.fromEntries(prefixes.filter((p) => p.category.trim() && p.prefix.trim()).map((p) => [p.category.trim(), p.prefix.trim().toUpperCase()])),
      cash_accounts: accounts.split(",").map((s) => s.trim()).filter(Boolean),
    };
    try {
      await api.patch("/settings/", body);
      toast.ok("Settings saved");
      invalidate("/settings", "/stock/categories");
    } catch (e) { setErrors(fieldErrors(e)); toast.error(e); }
  };
  const uploadLogo = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("logo", file);
    try { await api.patch("/settings/", fd); toast.ok("Logo updated"); invalidate("/settings"); } catch (err) { toast.error(err); }
  };
  const set = (k) => (e) => setV({ ...v, [k]: e.target.value });

  return (
    <div className="stack">
      <PageHead title="Settings" subtitle={owner ? "Shop-wide configuration (owner only)." : "Read-only — only the owner can change shop settings."}>
        {perms.day_close && <Link className="btn" to="/heads-of-account">Heads of account</Link>}
      </PageHead>
      <fieldset disabled={!owner} style={{ border: 0, padding: 0, margin: 0 }} className="stack">
        <Card title="Shop">
          <div className="form-grid">
            <Input label="Shop name" className="span-2" value={v.shop_name} onChange={set("shop_name")} />
            <Input label="Phone" value={v.phone} onChange={set("phone")} />
            <Input label="Invoice prefix" value={v.invoice_prefix} onChange={set("invoice_prefix")} />
            <TextArea label="Address" className="span-2" value={v.address} onChange={set("address")} />
            <TextArea label="Receipt footer" className="span-2" value={v.receipt_footer_text} onChange={set("receipt_footer_text")} />
            <div className="span-2 gap">
              {v.logo && <img src={v.logo} alt="Logo" style={{ maxHeight: 48 }} />}
              <label className="btn sm">Upload logo<input type="file" accept="image/*" hidden onChange={uploadLogo} /></label>
            </div>
          </div>
        </Card>
        <Card title="Pricing & limits">
          <div className="form-grid">
            <Select label="Sale gold value basis" value={v.sale_gold_basis} onChange={set("sale_gold_basis")}
              options={[{ value: "pasa", label: "Pasa × rate / 11.664" }, { value: "weight", label: "Gold weight × rate / 11.664" }]} />
            <NumInput label="Manager discount limit (Rs)" value={v.default_discount_limit_manager} onChange={set("default_discount_limit_manager")} />
            <NumInput label="Staff discount limit (Rs)" value={v.default_discount_limit_staff} onChange={set("default_discount_limit_staff")} />
            <NumInput label="Zakat rate %" value={v.zakat_rate_percent} onChange={set("zakat_rate_percent")} />
            <Input label="Cash accounts (comma separated)" className="span-2" value={accounts} onChange={(e) => setAccounts(e.target.value)} error={errors.cash_accounts} hint="e.g. shop_cash, MBI, bank" />
          </div>
        </Card>
        <Card title="Categories & item code prefixes" actions={owner && <Button size="sm" onClick={() => setPrefixes([...prefixes, { category: "", prefix: "" }])}>+ Category</Button>}>
          {errors.code_prefixes && <div className="alert error">{errors.code_prefixes}</div>}
          <div className="grid grid-auto">
            {prefixes.map((p, i) => (
              <div key={i} className="gap" style={{ flexWrap: "nowrap" }}>
                <input value={p.category} placeholder="Category" onChange={(e) => setPrefixes(prefixes.map((x, j) => (j === i ? { ...x, category: e.target.value } : x)))} />
                <input value={p.prefix} placeholder="R" style={{ width: 64 }} onChange={(e) => setPrefixes(prefixes.map((x, j) => (j === i ? { ...x, prefix: e.target.value } : x)))} />
              </div>
            ))}
          </div>
          <p className="small muted">Codes are generated as prefix + 4 digits (R0111, NS0027…). Prefixes must be unique letters.</p>
        </Card>
        {owner && <div><Button variant="primary" onClick={save}>Save settings</Button></div>}
      </fieldset>
      <ChangePassword />
    </div>
  );
}
