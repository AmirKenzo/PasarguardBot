import { Calendar, Coins, CreditCard, Package, User, Users, Zap } from "lucide-react";
import { Link } from "react-router-dom";
import { PageHeader } from "../../components/layout/PageHeader";
import { ErrorState, Skeleton } from "../../components/ui";
import { formatNumber, formatToman } from "../../lib/format";
import { panelReportsApi } from "../../api/panel";
import type { PanelRankRow } from "../../types/panel";
import { usePanelQuery } from "../../queries/usePanelApi";
import { IconMenuButton, MenuRow, SectionCard, StatTile } from "./components";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";
import { useState } from "react";

const periodLabels = (t: TFunction): Record<string, string> => ({
  today: t("common.today"),
  "3d": t("panel.reports.threeDays"),
  week: t("panel.reports.sevenDays"),
  month: t("panel.reports.thirtyDays"),
  quarter: t("panel.reports.ninetyDays"),
  year: t("panel.reports.oneYear"),
  all: t("panel.reports.allTime"),
});

export default function AdminReportsPage() {
  const { t } = useTranslation();
  const [period, setPeriod] = useState("today");

  const query = usePanelQuery(["reports", period], (auth) => panelReportsApi.getReports({ ...auth, period }));

  const totals = query.data?.totals;
  const totalRevenue = totals ? totals.manual_approved_sum + totals.auto_approved_sum : 0;

  return (
    <>
      <PageHeader
        title={t("panel.common.reports")}
        subtitle={t("panel.reports.subtitle")}
        action={
          <IconMenuButton
            icon={Calendar}
            title={t("panel.reports.period")}
            active
            width={160}
            heightEstimate={280}
          >
            {(close) => (
              <>
                {(query.data?.periods || ["today"]).map((value) => (
                  <MenuRow
                    key={value}
                    label={periodLabels(t)[value] || value}
                    active={value === period}
                    onClick={() => {
                      setPeriod(value);
                      close();
                    }}
                  />
                ))}
              </>
            )}
          </IconMenuButton>
        }
      />

      {query.isLoading || !totals ? (
        <div className="grid grid-cols-2 gap-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full rounded-lg" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-2 lg:grid-cols-3">
          <StatTile dense icon={Users} label={t("panel.reports.newUsers")} value={formatNumber(totals.new_users)} />
          <StatTile
            dense
            icon={Package}
            label={t("panel.reports.servicesSold")}
            value={formatNumber(totals.services_sold)}
            hint={t("panel.reports.trialCount", { count: formatNumber(totals.test_services) })}
          />
          <StatTile
            dense
            icon={Coins}
            label={t("panel.reports.totalRevenue")}
            value={formatToman(totalRevenue)}
            tone="primary"
          />
          <StatTile dense icon={CreditCard} label={t("panel.reports.cardTopUp")} value={formatToman(totals.manual_approved_sum)} />
          <StatTile dense icon={Zap} label={t("panel.reports.automaticTopUp")} value={formatToman(totals.auto_approved_sum)} />
          <StatTile
            dense
            label={t("panel.common.awaitingApproval")}
            value={formatToman(totals.pending_sum)}
            hint={t("panel.reports.invoiceCount", { count: formatNumber(totals.pending_count) })}
            tone={totals.pending_sum ? "warning" : "default"}
          />
        </div>
      )}

      {query.isError && <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />}

      <div className="grid gap-4 lg:grid-cols-2">
        <RankList
          title={t("panel.reports.topByTopUps")}
          rows={query.data?.top_recharge || []}
          loading={query.isLoading}
          emptyLabel={t("panel.reports.noTopUps")}
          valueLabel={(row) => formatToman(row.amount)}
          countLabel={(row) => t("panel.reports.invoiceCount", { count: formatNumber(row.count) })}
        />
        <RankList
          title={t("panel.reports.topByPurchases")}
          rows={query.data?.top_spenders || []}
          loading={query.isLoading}
          emptyLabel={t("panel.reports.noPurchases")}
          valueLabel={(row) => formatToman(row.amount)}
          countLabel={(row) => t("panel.reports.invoiceCount", { count: formatNumber(row.count) })}
        />
      </div>

      <RankList
        title={t("panel.reports.topByServiceCount")}
        description={t("panel.reports.allTimeNote")}
        rows={query.data?.top_service_counts || []}
        loading={query.isLoading}
        emptyLabel={t("panel.reports.noServices")}
        valueLabel={(row) => `${formatNumber(row.count)} ${t("panel.reports.serviceCount")}`}
      />
    </>
  );
}

function RankList({
  title,
  description,
  rows,
  loading,
  emptyLabel,
  valueLabel,
  countLabel,
}: {
  title: string;
  description?: string;
  rows: PanelRankRow[];
  loading: boolean;
  emptyLabel: string;
  valueLabel: (row: PanelRankRow) => string;
  countLabel?: (row: PanelRankRow) => string;
}) {
  return (
    <SectionCard title={title} description={description}>
      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-11 w-full rounded-md" />
          ))}
        </div>
      ) : rows.length ? (
        <div className="-mt-1 divide-y divide-border/60">
          {rows.map((row) => (
            <div key={row.rank} className="flex items-center gap-2.5 py-2 first:pt-0 last:pb-0">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-surface-2 text-[11px] font-semibold text-muted">
                {row.rank}
              </span>
              <Link
                to={row.user_id ? `/panel/users/${row.user_id}` : "#"}
                className="flex min-w-0 flex-1 items-center gap-1.5 text-xs font-medium text-text hover:text-primary"
              >
                <User size={12} className="shrink-0 text-muted" />
                <span className="ltr-field truncate">{row.user_id ?? "—"}</span>
              </Link>
              <div className="text-end">
                <div className="text-xs font-semibold text-text">{valueLabel(row)}</div>
                {countLabel && <div className="text-[11px] text-muted">{countLabel(row)}</div>}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="py-6 text-center text-sm text-muted">{emptyLabel}</p>
      )}
    </SectionCard>
  );
}
