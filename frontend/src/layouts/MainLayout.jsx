import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth, useGoldRate, useHotkeys, useLocalState, usePermissions } from "../hooks";
import { date, label, pkr } from "../utils/format";

function navFor(p) {
  return [
    { section: "Counter" },
    { to: "/", label: "Dashboard", end: true },
    { to: "/sales/new", label: "New sale", kbd: "Alt+N" },
    { to: "/invoices", label: "Invoices" },
    { to: "/advances", label: "Advances" },
    { to: "/stock", label: "Stock", kbd: "Alt+K" },
    { to: "/rates", label: "Gold rate" },
    { section: "Parties" },
    { to: "/customers", label: "Customers" },
    { to: "/suppliers", label: "Suppliers & karigar" },
    { section: "Accounts" },
    { to: "/cash-book", label: "Cash book", kbd: "Alt+D" },
    p.refining && { to: "/refining", label: "Old gold & refine" },
    p.reports && { to: "/reports", label: "Reports" },
    p.investors && { to: "/investors", label: "Investors" },
    p.zakat && { to: "/zakat", label: "Zakat" },
    { section: "Admin" },
    { to: "/settings", label: "Settings" },
    p.manage_users && { to: "/users", label: "Users" },
    p.audit_log && { to: "/audit-log", label: "Audit log" },
  ].filter(Boolean);
}

export default function MainLayout() {
  const { user, logout } = useAuth();
  const perms = usePermissions();
  const nav = useNavigate();
  const loc = useLocation();
  const { rate, isToday } = useGoldRate();
  const [open, setOpen] = useState(false);
  const [theme, setTheme] = useLocalState("alnoor.theme", "auto");

  useEffect(() => setOpen(false), [loc.pathname]);
  useEffect(() => {
    if (theme === "auto") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  useHotkeys({
    "alt+n": () => nav("/sales/new"),
    "alt+k": () => nav("/stock?focus=1"),
    "alt+d": () => nav("/cash-book?tab=day"),
  });

  return (
    <div className="app">
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <div className="brand">
          <div className="name">New Al-Noor Jewellers</div>
          <div className="sub">{user?.full_name} · {label(user?.role)}</div>
        </div>
        <nav className="nav">
          {navFor(perms).map((item, i) =>
            item.section ? (
              <div key={i} className="section">{item.section}</div>
            ) : (
              <NavLink key={item.to} to={item.to} end={item.end}>
                {item.label}
                {item.kbd && <span className="kbd hide-mobile">{item.kbd}</span>}
              </NavLink>
            ),
          )}
        </nav>
        <div className="foot gap">
          <button type="button" onClick={() => setTheme(theme === "auto" ? "dark" : theme === "dark" ? "light" : "auto")}>
            Theme: {theme}
          </button>
          <button type="button" onClick={logout}>Sign out</button>
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <button type="button" className="btn sm menu-btn" onClick={() => setOpen(!open)} aria-label="Menu">☰</button>
          <div className="spacer" />
          {rate ? (
            <NavLink to="/rates" className={`rate-chip ${isToday ? "" : "stale"}`} title="Gold rate per tola">
              <span className="hide-mobile">{isToday ? "Today" : `Last set ${date(rate.date)}`}</span>
              <span>Buy <b>{pkr(rate.buy_rate_per_tola)}</b></span>
              <span>Sell <b>{pkr(rate.sell_rate_per_tola)}</b></span>
            </NavLink>
          ) : (
            <NavLink to="/rates" className="rate-chip stale">Set today's gold rate</NavLink>
          )}
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
