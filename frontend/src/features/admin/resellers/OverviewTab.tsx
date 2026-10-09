import { AlertTriangle, CalendarClock, Flame, Power, TrendingUp, Users, Wallet } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Badge, Button, EmptyState, ErrorState, Skeleton } from "../../../components/ui";
import { panelResellersApi } from "../../../api/panel";
import { formatCompactToman, formatNumber, formatRelativeTime, formatToman, formatUnixDate } from "../../../lib/format";
import { usePanelQuery } from "../../../queries/usePanelApi";
import { SectionCard, StatTile, TrendChart } from "../components";
import { RESELLER_STATUSES } from "../../../types/panel";
import { EventList, StatusBadge } from "./parts";
import { STATUS_TONE, formatRunway, pricingLabels, pricingShortLabels, runwayTone, statusLabels } from "./labels";

type Navigate = (tab: string, extra?: Record<string, string>) => void;

export default function OverviewTab({ onNavigate }: { onNavigate: Navigate }) {
  const { t } = useTranslation();
  const query = usePanelQuery(["reseller-overview"], (auth) => panelResellersApi.getOverview(auth), {
    refetchInterval: 60_000,
  });

  if (query.isError) return <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />;
  if (!query.data) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-20 w-full" />
          ))}
        </div>
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  const data = query.data;
  const active = data.by_status.active || 0;
  const openAccounts = (extra: Record<string, string>) => onNavigate("accounts", extra);

  return (
    <div className="space-y-4">
      {!data.sale_enabled && (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-warning/30 bg-warning/10 px-4 py-3 text-sm">
          <Power size={16} className="shrink-0 text-warning" />
          <span className="flex-1 text-text">{t("panel.resellerHub.overview.saleOff")}</span>
          <Button size="sm" variant="secondary" onClick={() => onNavigate("settings")}>
            {t("panel.resellerHub.tabs.settings")}
          </Button>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile
          label={t("panel.resellerHub.overview.accounts")}
          value={formatNumber(data.total)}
          hint={t("panel.resellerHub.overview.activeCount", { count: formatNumber(active) })}
          icon={Users}
          tone="primary"
        />
        <StatTile
          label={t("panel.resellerHub.overview.burn")}
          value={`${formatCompactToman(data.burn_per_hour)}`}
          exactValue={formatToman(data.burn_per_hour)}
          hint={t("panel.resellerHub.overview.perHour")}
          icon={Flame}
          tone="warning"
        />
        <StatTile
          label={t("panel.resellerHub.overview.revenueToday")}
          value={formatCompactToman(data.revenue_today.total)}
          exactValue={formatToman(data.revenue_today.total)}
          hint={t("panel.resellerHub.overview.revenue7d", { amount: formatCompactToman(data.revenue_7d.total) })}
          icon={TrendingUp}
          tone="success"
        />
        <StatTile
          label={t("panel.resellerHub.overview.revenue30d")}
          value={formatCompactToman(data.revenue_30d.total)}
          exactValue={formatToman(data.revenue_30d.total)}
          hint={t("panel.resellerHub.overview.revenueSplit", {
            payg: formatCompactToman(data.revenue_30d.payg),
            sales: formatCompactToman(data.revenue_30d.sales),
          })}
          icon={Wallet}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <SectionCard
          className="lg:col-span-2"
          title={t("panel.resellerHub.overview.revenuePerDay")}
          description={t("panel.resellerHub.overview.revenuePerDayHint")}
        >
          <TrendChart
            points={data.series.map((point) => ({ ts: point.ts, value: point.payg + point.sales }))}
            format={formatToman}
            total={formatToman(data.series.reduce((sum, point) => sum + point.payg + point.sales, 0))}
          />
        </SectionCard>

        <SectionCard title={t("panel.resellerHub.overview.breakdown")}>
          <div className="space-y-4">
            <div className="flex flex-wrap gap-1.5">
              {RESELLER_STATUSES.filter((status) => data.by_status[status]).map((status) => (
                <button
                  key={status}
                  type="button"
                  onClick={() => openAccounts({ status })}
                  className="transition-opacity hover:opacity-80"
                >
                  <Badge tone={STATUS_TONE[status] || "muted"}>
                    {statusLabels(t)[status]} · {formatNumber(data.by_status[status] ?? 0)}
                  </Badge>
                </button>
              ))}
              {!data.total && <p className="text-sm text-muted">{t("panel.resellerHub.accountsEmpty")}</p>}
            </div>
            <div className="space-y-2">
              {Object.entries(data.by_mode).map(([mode, count]) => (
                <button
                  key={mode}
                  type="button"
                  onClick={() => openAccounts({ mode })}
                  className="flex w-full items-center gap-2 text-sm"
                >
                  <span className="w-36 shrink-0 truncate text-start text-muted" title={pricingLabels(t)[mode] || mode}>
                    {pricingShortLabels(t)[mode] || mode}
                  </span>
                  <span className="h-2 flex-1 overflow-hidden rounded-full bg-surface-2">
                    <span
                      className="block h-full rounded-full bg-primary"
                      style={{ width: `${data.total ? (count / data.total) * 100 : 0}%` }}
                    />
                  </span>
                  <span className="w-8 shrink-0 text-end font-medium text-text">{formatNumber(count)}</span>
                </button>
              ))}
            </div>
          </div>
        </SectionCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <SectionCard
          title={t("panel.resellerHub.overview.atRisk")}
          description={t("panel.resellerHub.overview.atRiskHint", { hours: data.low_runway_hours })}
        >
          {data.at_risk.length ? (
            <ul className="divide-y divide-border/60">
              {data.at_risk.map((row) => (
                <li key={row.telegram_id}>
                  <button
                    type="button"
                    onClick={() => openAccounts({ q: String(row.telegram_id) })}
                    className="flex w-full items-center gap-3 py-2.5 text-start"
                  >
                    <AlertTriangle
                      size={16}
                      className={`shrink-0 ${runwayTone(row.hours_left, data.low_runway_hours) === "danger" ? "text-danger" : "text-warning"}`}
                    />
                    <div className="min-w-0 flex-1">
                      <p className="ltr-field truncate text-sm font-medium text-text">{row.telegram_id}</p>
                      <p className="truncate text-xs text-muted">
                        {row.accounts.join(t("panel.common.listSeparator"))} ·{" "}
                        {t("panel.resellerHub.overview.burnRow", { amount: formatToman(row.burn_per_hour) })}
                      </p>
                    </div>
                    <div className="shrink-0 text-end">
                      <Badge tone={runwayTone(row.hours_left, data.low_runway_hours)}>
                        {formatRunway(t, row.hours_left)}
                      </Badge>
                      <p className="mt-1 text-xs text-muted">{formatToman(row.balance)}</p>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState title={t("panel.resellerHub.overview.atRiskEmpty")} />
          )}
        </SectionCard>

        <SectionCard
          title={t("panel.resellerHub.overview.expiring")}
          description={t("panel.resellerHub.overview.expiringHint")}
        >
          {data.expiring.length ? (
            <ul className="divide-y divide-border/60">
              {data.expiring.map((row) => (
                <li key={row.code}>
                  <button
                    type="button"
                    onClick={() => openAccounts({ open: String(row.code) })}
                    className="flex w-full items-center gap-3 py-2.5 text-start"
                  >
                    <CalendarClock size={16} className="shrink-0 text-muted" />
                    <div className="min-w-0 flex-1">
                      <p className="ltr-field truncate text-sm font-medium text-text">{row.username}</p>
                      <p className="truncate text-xs text-muted" title={formatUnixDate(row.expiration_time)}>
                        {row.purge_at
                          ? t("panel.resellerHub.overview.purgeAt", { when: formatUnixDate(row.purge_at) })
                          : t("panel.resellerHub.overview.expiresAt", { when: formatUnixDate(row.expiration_time) })}
                      </p>
                    </div>
                    <StatusBadge status={row.status} />
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState title={t("panel.resellerHub.overview.expiringEmpty")} />
          )}
        </SectionCard>
      </div>

      <SectionCard
        title={t("panel.resellerHub.overview.recentEvents")}
        actions={
          <Button size="sm" variant="ghost" onClick={() => onNavigate("billing", { view: "events" })}>
            {t("panel.resellerHub.overview.allEvents")}
          </Button>
        }
      >
        <EventList
          events={data.recent_events}
          showAccount
          onOpenAccount={(code) => openAccounts({ open: String(code) })}
        />
        {data.recent_events.length > 0 && (
          <p className="mt-2 text-end text-[11px] text-muted">
            {t("panel.resellerHub.overview.updated", { when: formatRelativeTime(Math.floor(query.dataUpdatedAt / 1000)) })}
          </p>
        )}
      </SectionCard>
    </div>
  );
}
