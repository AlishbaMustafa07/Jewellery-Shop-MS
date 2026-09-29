import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { errorMessage } from "../../api/client";
import { Alert, Button, Input } from "../../components/ui";
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
      <form className="card" onSubmit={submit}>
        <div className="card-body stack">
          <div className="center">
            <svg width="44" height="44" viewBox="0 0 64 64" aria-hidden="true">
              <circle cx="32" cy="36" r="20" fill="none" stroke="var(--accent)" strokeWidth="6" />
              <path d="M22 14 L32 4 L42 14 L32 22 Z" fill="var(--accent)" />
            </svg>
            <h1 style={{ marginTop: 6 }}>New Al-Noor Jewellers</h1>
            <div className="muted small">Shop management system</div>
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
  );
}
