import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";
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
import { formatCompactToman, formatNumber, formatToman } from "../../lib/format";
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
            <p className="text-xs font-medium text-primary-text/70">{t("panel.dashboard.revenueToday")}</p>
            <p className="mt-1.5 text-[1.75rem] font-extrabold leading-none tracking-tight" dir="ltr">
              {formatToman(stats.income_today)}
            </p>
          </div>
          {stats.pending_tx > 0 && (
            <Link
              to="/panel/transactions"
              className="flex shrink-0 items-center gap-1 rounded-full bg-white/15 px-3 py-1.5 text-xs font-medium transition-colors hover:bg-white/25"
            >
              {formatNumber(stats.pending_tx)} {t("panel.dashboard.pendingTransactions")}
              <ChevronLeft size={13} />
            </Link>
          )}
        </div>

        <div className="relative mt-5 flex flex-wrap items-center gap-2 border-t border-white/15 pt-4 text-xs text-primary-text/85">
          <HeroStat icon={TrendingUp} value={formatToman(stats.income_month)} label={t("panel.dashboard.revenueThirtyDays")} />
          <HeroStat icon={Users} value={formatNumber(stats.users_total)} label={t("common.user")} />
          <HeroStat icon={Boxes} value={formatNumber(stats.services_active)} label={t("panel.dashboard.activeService")} />
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
        <StatTile
          label={t("panel.dashboard.walletBalances")}
          value={formatCompactToman(stats.wallet_total)}
          exactValue={formatToman(stats.wallet_total)}
          icon={Wallet}
        />
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
        <StatTile
          label={t("panel.dashboard.revenueThirtyDays")}
          value={formatCompactToman(stats.income_month)}
          exactValue={formatToman(stats.income_month)}
          icon={CreditCard}
          tone="primary"
        />
      </div>

      <SectionCard title={t("panel.dashboard.revenuePerDay")} description={t("panel.dashboard.lastFourteenDays")}>
        <TrendChart
          points={series.map((point) => ({ ts: point.ts, value: point.revenue }))}
          format={formatToman}
          total={formatToman(series.reduce((sum, point) => sum + point.revenue, 0))}
        />
      </SectionCard>

      <SectionCard title={t("panel.dashboard.signupsPerDay")} description={t("panel.dashboard.lastFourteenDays")}>
        <TrendChart
          points={series.map((point) => ({ ts: point.ts, value: point.signups }))}
          format={(value) => t("panel.dashboard.userCount", { count: formatNumber(value) })}
          total={t("panel.dashboard.userCount", { count: formatNumber(series.reduce((sum, point) => sum + point.signups, 0)) })}
          tone="accent"
        />
      </SectionCard>
    </>
  );
}

function HeroStat({ icon: Icon, value, label }: { icon: LucideIcon; value: string; label: string }) {
  return (
    <div className="flex items-center gap-2 rounded-lg bg-white/10 px-2.5 py-1.5">
      <Icon size={13} className="shrink-0 text-primary-text/70" />
      <div className="leading-tight">
        <p className="font-semibold text-primary-text" dir="ltr">
          {value}
        </p>
        <p className="text-[10px] text-primary-text/70">{label}</p>
      </div>
    </div>
  );
}
