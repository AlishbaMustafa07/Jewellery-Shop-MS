import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Loading } from "./components/ui";
import LoginPage from "./features/auth/LoginPage";
import CashBookPage from "./features/cashbook/CashBookPage";
import HeadsPage from "./features/cashbook/HeadsPage";
import CustomerDetailPage from "./features/customers/CustomerDetailPage";
import CustomersPage from "./features/customers/CustomersPage";
import DashboardPage from "./features/dashboard/DashboardPage";
import InvestorDetailPage from "./features/investors/InvestorDetailPage";
import InvestorsPage from "./features/investors/InvestorsPage";
import ZakatPage from "./features/investors/ZakatPage";
import RatesPage from "./features/rates/RatesPage";
import RefiningPage from "./features/refining/RefiningPage";
import ReportsPage from "./features/reports/ReportsPage";
import AdvancesPage from "./features/sales/AdvancesPage";
import InvoiceDetailPage from "./features/sales/InvoiceDetailPage";
import InvoicesPage from "./features/sales/InvoicesPage";
import NewSalePage from "./features/sales/NewSalePage";
import AuditLogPage from "./features/settings/AuditLogPage";
import SettingsPage from "./features/settings/SettingsPage";
import UsersPage from "./features/settings/UsersPage";
import StockDetailPage from "./features/stock/StockDetailPage";
import StockFormPage from "./features/stock/StockFormPage";
import StockPage from "./features/stock/StockPage";
import SupplierDetailPage from "./features/suppliers/SupplierDetailPage";
import SuppliersPage from "./features/suppliers/SuppliersPage";
import { useAuth, usePermissions } from "./hooks";
import MainLayout from "./layouts/MainLayout";
import NotFoundPage from "./pages/NotFoundPage";

function RequireAuth({ children }) {
  const { user, ready } = useAuth();
  const loc = useLocation();
  if (!ready) return <Loading />;
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname + loc.search }} />;
  return children;
}

/** Hides a route from roles without the permission flag (the API enforces it too). */
function Allow({ perm, children }) {
  const p = usePermissions();
  if (perm && !p[perm]) return <NotFoundPage message="Your role does not have access to this page." />;
  return children;
}

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth><MainLayout /></RequireAuth>}>
        <Route index element={<DashboardPage />} />
        <Route path="sales/new" element={<NewSalePage />} />
        <Route path="invoices" element={<InvoicesPage />} />
        <Route path="invoices/:id" element={<InvoiceDetailPage />} />
        <Route path="advances" element={<AdvancesPage />} />
        <Route path="stock" element={<StockPage />} />
        <Route path="stock/new" element={<StockFormPage />} />
        <Route path="stock/:id" element={<StockDetailPage />} />
        <Route path="stock/:id/edit" element={<StockFormPage />} />
        <Route path="rates" element={<RatesPage />} />
        <Route path="customers" element={<CustomersPage />} />
        <Route path="customers/:id" element={<CustomerDetailPage />} />
        <Route path="suppliers" element={<SuppliersPage />} />
        <Route path="suppliers/:id" element={<SupplierDetailPage />} />
        <Route path="cash-book" element={<CashBookPage />} />
        <Route path="heads-of-account" element={<HeadsPage />} />
        <Route path="refining" element={<Allow perm="refining"><RefiningPage /></Allow>} />
        <Route path="reports" element={<Allow perm="reports"><ReportsPage /></Allow>} />
        <Route path="investors" element={<Allow perm="investors"><InvestorsPage /></Allow>} />
        <Route path="investors/:id" element={<Allow perm="investors"><InvestorDetailPage /></Allow>} />
        <Route path="zakat" element={<Allow perm="zakat"><ZakatPage /></Allow>} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="users" element={<Allow perm="manage_users"><UsersPage /></Allow>} />
        <Route path="audit-log" element={<Allow perm="audit_log"><AuditLogPage /></Allow>} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
