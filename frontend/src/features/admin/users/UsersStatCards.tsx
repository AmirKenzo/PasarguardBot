import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { CalendarRange, Minus, ShoppingBag, TrendingDown, TrendingUp, UserPlus, Users } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Skeleton } from "../../../components/ui";
import { formatNumber } from "../../../lib/format";
import type { PanelUsersStatsResponse } from "../../../types/panel";

type Tone = "primary" | "accent" | "success" | "warning";

const ICON_CLASSES: Record<Tone, string> = {
  primary: "bg-primary/12 text-primary",
  accent: "bg-accent/12 text-accent",
  success: "bg-success/12 text-success",
  warning: "bg-warning/12 text-warning",
};

function percentOf(part: number, whole: number): number {
  return whole > 0 ? Math.round((part / whole) * 100) : 0;
}

interface StatCardProps {
  label: ReactNode;
  icon: LucideIcon;
  tone: Tone;
  value: ReactNode;
  footer: ReactNode;
  highlight?: boolean;
}

function StatCard({ label, icon: Icon, tone, value, footer, highlight = false }: StatCardProps) {
  return (
    <div
      className={`flex min-w-0 flex-col rounded-2xl border p-3 sm:p-3.5 ${
        highlight ? "border-primary/40 bg-primary/[0.06]" : "border-border bg-surface"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="min-w-0 truncate text-2xs text-muted sm:text-xs">{label}</span>
        <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${ICON_CLASSES[tone]}`}>
          <Icon size={15} />
        </span>
      </div>
      <div className="mt-1.5 text-xl font-bold leading-tight text-text sm:text-2xl">{value}</div>
      <div className="mt-1.5 flex min-h-[22px] items-end text-2xs text-muted">{footer}</div>
    </div>
  );
}

function DailyBars({ values }: { values: number[] }) {
  const { t } = useTranslation();
  const max = Math.max(0, ...values);
  return (
    <div className="flex h-[22px] w-full items-end gap-1" aria-hidden>
      {values.map((value, index) => {
        const last = index === values.length - 1;
        const height = max > 0 ? Math.max(12, Math.round((value / max) * 100)) : 12;
        return (
          <span
            key={index}
            title={t("panel.users.statDayBar", { count: value })}
            className={`flex-1 rounded-[3px] ${last ? "bg-primary" : "bg-primary/30"}`}
            style={{ height: `${height}%` }}
          />
        );
      })}
    </div>
  );
}

function Trend({ current, previous }: { current: number; previous: number }) {
  const { t } = useTranslation();
  const diff = current - previous;
  if (diff === 0) {
    return (
      <span className="flex items-center gap-1">
        <Minus size={12} />
        {t("panel.users.statTrendSame")}
      </span>
    );
  }
  const up = diff > 0;
  const Icon = up ? TrendingUp : TrendingDown;
  return (
    <span className={`flex items-center gap-1 ${up ? "text-success" : "text-danger"}`}>
      <Icon size={12} className="shrink-0" />
      <span className="truncate">
        {t(up ? "panel.users.statTrendUp" : "panel.users.statTrendDown", { diff: formatNumber(Math.abs(diff)) })}
      </span>
    </span>
  );
}

const GRID = "grid grid-cols-2 gap-2.5 sm:grid-cols-4";

export function UsersStatCards({ stats }: { stats?: PanelUsersStatsResponse }) {
  const { t } = useTranslation();

  if (!stats) {
    return (
      <div className={GRID}>
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-[104px] w-full rounded-2xl" />
        ))}
      </div>
    );
  }

  return (
    <div className={GRID}>
      <StatCard
        highlight
        tone="primary"
        icon={UserPlus}
        label={
          <>
            <span className="sm:hidden">{t("panel.users.statNew24hShort")}</span>
            <span className="hidden sm:inline">{t("panel.users.statNew24h")}</span>
          </>
        }
        value={formatNumber(stats.new_24h)}
        footer={<Trend current={stats.new_24h} previous={stats.new_prev_24h} />}
      />
      <StatCard
        tone="accent"
        icon={CalendarRange}
        label={t("panel.users.statNew7d")}
        value={formatNumber(stats.new_7d)}
        footer={<DailyBars values={stats.new_daily} />}
      />
      <StatCard
        tone="success"
        icon={ShoppingBag}
        label={t("panel.users.statBuyers")}
        value={t("panel.users.statPercent", { value: formatNumber(percentOf(stats.new_buyers_24h, stats.new_24h)) })}
        footer={
          <span className="truncate">
            {t("panel.users.statBuyersHint", {
              buyers: formatNumber(stats.new_buyers_24h),
              total: formatNumber(stats.new_24h),
            })}
          </span>
        }
      />
      <StatCard
        tone="warning"
        icon={Users}
        label={t("panel.users.statActive")}
        value={formatNumber(stats.active)}
        footer={
          <span className="truncate">
            {t("panel.users.statActiveHint", { percent: formatNumber(percentOf(stats.active, stats.total)) })}
          </span>
        }
      />
    </div>
  );
}
