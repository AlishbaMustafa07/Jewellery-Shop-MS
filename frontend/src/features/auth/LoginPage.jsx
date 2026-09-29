import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { errorMessage } from "../../api/client";
import { Alert, BrandMark, Button, Input } from "../../components/ui";
import { useAuth } from "../../hooks";

export default function LoginPage() {
  const { login } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const user = await login(username.trim(), password);
      const dest = loc.state?.from || (user.role === "salesperson" ? "/sales/new" : "/");
      nav(dest, { replace: true });
    } catch (err) {
      setError(err?.response?.status === 401 ? "Wrong username or password." : errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth">
      <div className="auth-shell">
        <div className="auth-brand">
          <BrandMark size={56} />
          <div>
            <h1 className="name">New Al-Noor Jewellers</h1>
            <div className="sub">Shop management system</div>
          </div>
          <div className="pitch">Sales, stock, gold rates, cash book and reports — all in one place, built for the counter.</div>
        </div>
        <div className="auth-form">
          <form className="card" onSubmit={submit}>
            <div className="card-body stack">
              <div>
                <h1>Welcome back</h1>
                <div className="muted small" style={{ marginTop: 4 }}>Sign in to continue</div>
              </div>
              {error && <Alert kind="error">{error}</Alert>}
              <Input label="Username" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus
                autoComplete="username" required />
              <Input label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password" required />
              <Button type="submit" variant="primary" className="lg" style={{ width: "100%" }} disabled={busy}>
                {busy ? "Signing in…" : "Sign in"}
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
