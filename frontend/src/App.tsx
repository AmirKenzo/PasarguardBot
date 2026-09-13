import { lazy, Suspense, useEffect } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { Spinner } from "./components/ui/Spinner";
import { useAuth } from "./context/AuthContext";
import { useTelegramViewportFix } from "./hooks/useTelegramViewportFix";
import { AdminGuard } from "./features/admin/AdminGuard";
import { clearPanelRedirect, peekPanelRedirect, rememberPanelRedirect } from "./features/admin/redirect";

const LoginPage = lazy(() => import("./features/auth/LoginPage"));
const DashboardPage = lazy(() => import("./features/dashboard/DashboardPage"));
const ProfilePage = lazy(() => import("./features/profile/ProfilePage"));
const HelpPage = lazy(() => import("./features/help/HelpPage"));
const BalanceHubPage = lazy(() => import("./features/balance/BalanceHubPage"));
const ManualDeposit = lazy(() => import("./features/balance/ManualDeposit"));
const CryptoDeposit = lazy(() => import("./features/balance/CryptoDeposit"));
const TransactionsPage = lazy(() => import("./features/balance/TransactionsPage"));
const ServicesListPage = lazy(() => import("./features/services/ServicesListPage"));
const ServiceDetailPage = lazy(() => import("./features/services/ServiceDetailPage"));
const RenewFlow = lazy(() => import("./features/services/RenewFlow"));
const ExtendTimeFlow = lazy(() => import("./features/services/ExtendTimeFlow"));
const ExtraVolumeFlow = lazy(() => import("./features/services/ExtraVolumeFlow"));
const BuyWizardPage = lazy(() => import("./features/buy/BuyWizardPage"));

const AdminShell = lazy(() => import("./features/admin/AdminShell"));
const AdminDashboardPage = lazy(() => import("./features/admin/DashboardPage"));
const AdminUsersPage = lazy(() => import("./features/admin/UsersPage"));
const AdminUserDetailPage = lazy(() => import("./features/admin/UserDetailPage"));
const AdminServicesPage = lazy(() => import("./features/admin/ServicesPage"));
const AdminTransactionsPage = lazy(() => import("./features/admin/TransactionsPage"));
const AdminPaymentsPage = lazy(() => import("./features/admin/PaymentsPage"));
const AdminPanelsPage = lazy(() => import("./features/admin/PanelsPage"));
const AdminPlansPage = lazy(() => import("./features/admin/PlansPage"));
const AdminResellersPage = lazy(() => import("./features/admin/ResellersPage"));
const AdminResellerPlansPage = lazy(() => import("./features/admin/ResellerPlansPage"));
const AdminDiscountsPage = lazy(() => import("./features/admin/DiscountsPage"));
const AdminReferralPage = lazy(() => import("./features/admin/ReferralPage"));
const AdminBroadcastPage = lazy(() => import("./features/admin/BroadcastPage"));
const AdminChannelsPage = lazy(() => import("./features/admin/ChannelsPage"));
const AdminTextsPage = lazy(() => import("./features/admin/TextsPage"));
const AdminKeyboardPage = lazy(() => import("./features/admin/KeyboardPage"));
const AdminSettingsPage = lazy(() => import("./features/admin/SettingsPage"));
const AdminReportsPage = lazy(() => import("./features/admin/ReportsPage"));
const AdminToolsPage = lazy(() => import("./features/admin/ToolsPage"));
const AdminAuditPage = lazy(() => import("./features/admin/AuditPage"));

function Loader() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-bg">
      <Spinner size={28} className="text-primary" />
    </div>
  );
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

/** Like ProtectedRoute, but remembers the panel page the admin was opening so
 *  the login lands back there instead of on the user dashboard. */
function PanelRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  const location = useLocation();
  if (!isAuthenticated) {
    rememberPanelRedirect(location.pathname + location.search);
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

/** Send a freshly authenticated user to the page they were reaching for.
 *
 *  LoginPage navigates to "/" itself once the session is set, so this rides
 *  along with the authenticated shell rather than sitting on the login route:
 *  by the time it mounts the redirect has already happened, and it carries on
 *  to the panel page the admin actually opened. */
function PanelReturn() {
  const navigate = useNavigate();
  useEffect(() => {
    const target = peekPanelRedirect();
    if (!target) return;
    clearPanelRedirect();
    navigate(target, { replace: true });
  }, [navigate]);
  return null;
}

export default function App() {
  const { isAuthenticated, loading } = useAuth();
  useTelegramViewportFix();

  if (loading) return <Loader />;

  return (
    <Suspense fallback={<Loader />}>
      <Routes>
        <Route
          path="/login"
          element={isAuthenticated ? <Navigate to="/" replace /> : <LoginPage />}
        />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <>
                <PanelReturn />
                <AppShell />
              </>
            </ProtectedRoute>
          }
        >
          <Route index element={<DashboardPage />} />
          <Route path="services" element={<ServicesListPage />} />
          <Route path="services/:code" element={<ServiceDetailPage />} />
          <Route path="services/:code/renew" element={<RenewFlow />} />
          <Route path="services/:code/extend-time" element={<ExtendTimeFlow />} />
          <Route path="services/:code/extra-volume" element={<ExtraVolumeFlow />} />
          <Route path="buy" element={<BuyWizardPage />} />
          <Route path="balance" element={<BalanceHubPage />} />
          <Route path="balance/transactions" element={<TransactionsPage />} />
          <Route path="balance/manual" element={<ManualDeposit />} />
          <Route path="balance/crypto" element={<CryptoDeposit />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="help" element={<HelpPage />} />
        </Route>
        <Route
          path="/panel"
          element={
            <PanelRoute>
              <AdminGuard>
                <AdminShell />
              </AdminGuard>
            </PanelRoute>
          }
        >
          <Route index element={<AdminDashboardPage />} />
          <Route path="users" element={<AdminUsersPage />} />
          <Route path="users/:userId" element={<AdminUserDetailPage />} />
          <Route path="services" element={<AdminServicesPage />} />
          <Route path="transactions" element={<AdminTransactionsPage />} />
          <Route path="payments" element={<AdminPaymentsPage />} />
          <Route path="panels" element={<AdminPanelsPage />} />
          <Route path="plans" element={<AdminPlansPage />} />
          <Route path="resellers" element={<AdminResellersPage />} />
          <Route path="reseller-plans" element={<AdminResellerPlansPage />} />
          <Route path="discounts" element={<AdminDiscountsPage />} />
          <Route path="referral" element={<AdminReferralPage />} />
          <Route path="broadcast" element={<AdminBroadcastPage />} />
          <Route path="channels" element={<AdminChannelsPage />} />
          <Route path="texts" element={<AdminTextsPage />} />
          <Route path="keyboard" element={<AdminKeyboardPage />} />
          <Route path="settings" element={<AdminSettingsPage />} />
          <Route path="reports" element={<AdminReportsPage />} />
          <Route path="tools" element={<AdminToolsPage />} />
          <Route path="audit" element={<AdminAuditPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
