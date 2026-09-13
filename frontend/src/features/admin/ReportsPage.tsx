import { useState } from "react";
import { PageHeader } from "../../components/layout/PageHeader";
import { ErrorState, Skeleton } from "../../components/ui";
import { formatNumber, formatToman } from "../../lib/format";
import { panelReportsApi } from "../../api/panel";
import type { PanelRankRow } from "../../types/panel";
import { usePanelQuery } from "../../queries/usePanelApi";
import { DataTable, SectionCard, SelectField, StatTile } from "./components";
import type { Column } from "./components";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

const periodLabels = (t: TFunction): Record<string, string> => ({
  today: t("common.today"),
  week: t("panel.reports.sevenDays"),
  month: t("panel.reports.thirtyDays"),
});

export default function AdminReportsPage() {
  const { t } = useTranslation();
  const [period, setPeriod] = useState("today");

  const query = usePanelQuery(["reports", period], (auth) => panelReportsApi.getReports({ ...auth, period }));

  const moneyColumns: Column<PanelRankRow>[] = [
    { key: "rank", header: "#", cell: (row) => row.rank },
    {
      key: "user",
      header: t("common.user"),
      cell: (row) => <code className="ltr-field text-xs">{row.user_id ?? "—"}</code>,
    },
    { key: "amount", header: t("panel.common.amount"), cell: (row) => formatToman(row.amount) },
    { key: "count", header: t("panel.reports.count"), secondary: true, cell: (row) => formatNumber(row.count) },
  ];

  const countColumns: Column<PanelRankRow>[] = [
    { key: "rank", header: "#", cell: (row) => row.rank },
    {
      key: "user",
      header: t("common.user"),
      cell: (row) => <code className="ltr-field text-xs">{row.user_id ?? "—"}</code>,
    },
    { key: "count", header: t("panel.reports.serviceCount"), cell: (row) => formatNumber(row.count) },
  ];

  if (query.isError) {
    return <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />;
  }

  const totals = query.data?.totals;

  return (
    <>
      <PageHeader
        title={t("panel.common.reports")}
        subtitle={t("panel.reports.subtitle")}
        action={
          <div className="w-32">
            <SelectField
              options={(query.data?.periods || ["today"]).map((value) => ({
                value,
                label: periodLabels(t)[value] || value,
              }))}
              value={period}
              onChange={(event) => setPeriod(event.target.value)}
            />
          </div>
        }
      />

      {query.isLoading || !totals ? (
        <Skeleton className="h-24 w-full" />
      ) : (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
          <StatTile label={t("panel.reports.newUsers")} value={formatNumber(totals.new_users)} />
          <StatTile
            label={t("panel.reports.servicesSold")}
            value={formatNumber(totals.services_sold)}
            hint={t("panel.reports.trialCount", { count: formatNumber(totals.test_services) })}
          />
          <StatTile label={t("panel.reports.cardTopUp")} value={formatToman(totals.manual_approved_sum)} tone="primary" />
          <StatTile label={t("panel.reports.automaticTopUp")} value={formatToman(totals.auto_approved_sum)} />
          <StatTile
            label={t("panel.common.awaitingApproval")}
            value={formatToman(totals.pending_sum)}
            hint={t("panel.reports.invoiceCount", { count: formatNumber(totals.pending_count) })}
            tone={totals.pending_sum ? "warning" : "default"}
          />
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <SectionCard title={t("panel.reports.topByTopUps")}>
          <DataTable
            columns={moneyColumns}
            rows={query.data?.top_recharge || []}
            rowKey={(row) => row.rank}
            loading={query.isLoading}
            emptyTitle={t("panel.reports.noTopUps")}
          />
        </SectionCard>
        <SectionCard title={t("panel.reports.topByPurchases")}>
          <DataTable
            columns={moneyColumns}
            rows={query.data?.top_spenders || []}
            rowKey={(row) => row.rank}
            loading={query.isLoading}
            emptyTitle={t("panel.reports.noPurchases")}
          />
        </SectionCard>
      </div>

      <SectionCard title={t("panel.reports.topByServiceCount")} description={t("panel.reports.allTimeNote")}>
        <DataTable
          columns={countColumns}
          rows={query.data?.top_service_counts || []}
          rowKey={(row) => row.rank}
          loading={query.isLoading}
          emptyTitle={t("panel.reports.noServices")}
        />
      </SectionCard>
    </>
  );
}
