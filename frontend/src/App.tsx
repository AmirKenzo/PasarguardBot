import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { Spinner } from "./components/ui/Spinner";
import { useAuth } from "./context/AuthContext";

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
const BuyWizardPage = lazy(() => import("./features/buy/BuyWizardPage"));

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

export default function App() {
  const { isAuthenticated, loading } = useAuth();

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
              <AppShell />
            </ProtectedRoute>
          }
        >
          <Route index element={<DashboardPage />} />
          <Route path="services" element={<ServicesListPage />} />
          <Route path="services/:code" element={<ServiceDetailPage />} />
          <Route path="services/:code/renew" element={<RenewFlow />} />
          <Route path="buy" element={<BuyWizardPage />} />
          <Route path="balance" element={<BalanceHubPage />} />
          <Route path="balance/transactions" element={<TransactionsPage />} />
          <Route path="balance/manual" element={<ManualDeposit />} />
          <Route path="balance/crypto" element={<CryptoDeposit />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="help" element={<HelpPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
