import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Ban,
  Boxes,
  ChevronLeft,
  CreditCard,
  Receipt,
  Server,
  TrendingUp,
  Users,
  Wallet,
} from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { ErrorState, Skeleton } from "../../components/ui";
import { formatNumber, formatToman } from "../../lib/format";
import { panelDashboardApi } from "../../api/panel";
import { usePanelQuery } from "../../queries/usePanelApi";
import { SectionCard, StatTile, TrendChart } from "./components";
import { useTranslation } from "react-i18next";

export default function AdminDashboardPage() {
  const { t } = useTranslation();
  const { data, isLoading, isError, error, refetch } = usePanelQuery(["dashboard"], (auth) =>
    panelDashboardApi.getDashboard(auth)
  );

  if (isLoading) {
    return (
      <>
        <PageHeader title={t("panel.common.dashboard")} subtitle={t("panel.dashboard.subtitle")} />
        <Skeleton className="mb-4 h-40 w-full rounded-lg" />
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, index) => (
            <Skeleton key={index} className="h-24 w-full rounded-lg" />
          ))}
        </div>
      </>
    );
  }

  if (isError || !data) {
    return (
      <>
        <PageHeader title={t("panel.common.dashboard")} />
        <ErrorState message={error?.message || t("panel.dashboard.statsFailed")} onRetry={() => void refetch()} />
      </>
    );
  }

  const { stats, series } = data;

  return (
    <>
      <PageHeader title={t("panel.common.dashboard")} subtitle={t("panel.dashboard.subtitle")} />

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
        className="relative mb-4 overflow-hidden rounded-lg bg-gradient-to-br from-primary to-primary-strong p-5 text-primary-text shadow-md shadow-primary/25"
      >
        <div className="pointer-events-none absolute -left-8 -top-14 h-36 w-36 rounded-full bg-white/10 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-14 -right-6 h-32 w-32 rounded-full bg-white/10 blur-3xl" />

        <div className="relative flex items-start justify-between gap-3">
          <div>
            <p className="text-xs text-primary-text/70">{t("panel.dashboard.revenueToday")}</p>
            <p className="mt-1 text-2xl font-extrabold tracking-tight" dir="ltr">
              {formatToman(stats.income_today)}
            </p>
          </div>
          {stats.pending_tx > 0 && (
            <Link
              to="/panel/transactions"
              className="flex shrink-0 items-center gap-1 rounded-md bg-white/15 px-3 py-2 text-xs font-medium transition-colors hover:bg-white/25"
            >
              {formatNumber(stats.pending_tx)} {t("panel.dashboard.pendingTransactions")}
              <ChevronLeft size={14} />
            </Link>
          )}
        </div>

        <div className="relative mt-5 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-primary-text/80">
          <span className="flex items-center gap-1.5">
            <TrendingUp size={13} />
            {t("panel.dashboard.revenueThirtyDays")}: {formatToman(stats.income_month)}
          </span>
          <span className="flex items-center gap-1.5">
            <Users size={13} />
            {formatNumber(stats.users_total)} {t("common.user")}
          </span>
          <span className="flex items-center gap-1.5">
            <Boxes size={13} />
            {formatNumber(stats.services_active)} {t("panel.dashboard.activeService")}
          </span>
        </div>
      </motion.div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile
          label={t("panel.dashboard.totalUsers")}
          value={formatNumber(stats.users_total)}
          hint={t("panel.dashboard.todayCount", { count: formatNumber(stats.users_today) })}
          icon={Users}
          tone="primary"
        />
        <StatTile
          label={t("panel.dashboard.blockedUsers")}
          value={formatNumber(stats.users_blocked)}
          icon={Ban}
          tone={stats.users_blocked ? "warning" : "default"}
        />
        <StatTile label={t("panel.dashboard.walletBalances")} value={formatToman(stats.wallet_total)} icon={Wallet} />
        <StatTile
          label={t("panel.common.awaitingApproval")}
          value={formatNumber(stats.pending_tx)}
          icon={Receipt}
          tone={stats.pending_tx ? "warning" : "default"}
        />
        <StatTile
          label={t("panel.dashboard.activeServices")}
          value={formatNumber(stats.services_active)}
          hint={t("panel.dashboard.expiredCount", { count: formatNumber(stats.services_expired) })}
          icon={Boxes}
          tone="success"
        />
        <StatTile label={t("panel.dashboard.totalServices")} value={formatNumber(stats.services_total)} icon={Boxes} />
        <StatTile
          label={t("panel.common.panels")}
          value={formatNumber(stats.panels_total)}
          hint={t("panel.dashboard.activeResellers", { count: formatNumber(stats.resellers_active) })}
          icon={Server}
        />
        <StatTile label={t("panel.dashboard.revenueThirtyDays")} value={formatToman(stats.income_month)} icon={CreditCard} tone="primary" />
      </div>

      <SectionCard title={t("panel.dashboard.revenuePerDay")} description={t("panel.dashboard.lastFourteenDays")}>
        <TrendChart points={series.map((point) => ({ ts: point.ts, value: point.revenue }))} format={formatToman} />
      </SectionCard>

      <SectionCard title={t("panel.dashboard.signupsPerDay")} description={t("panel.dashboard.lastFourteenDays")}>
        <TrendChart
          points={series.map((point) => ({ ts: point.ts, value: point.signups }))}
          format={(value) => t("panel.dashboard.userCount", { count: formatNumber(value) })}
          tone="accent"
        />
      </SectionCard>
    </>
  );
}
