import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { useTranslation } from "react-i18next";
import { UsageAreaChart } from "../../components/UsageAreaChart";
import { Card } from "../../components/ui/Card";
import { Sheet } from "../../components/ui/Sheet";
import { Spinner } from "../../components/ui/Spinner";
import { SegmentedControl } from "../../components/ui/Select";
import { formatBytes } from "../../lib/format";
import { useUsageChartQuery } from "../../queries/useServices";

export interface UsageChartPanelProps {
  code: number;
  embedded?: boolean;
}

export function UsageChartPanel({ code, embedded = false }: UsageChartPanelProps) {
  const { t } = useTranslation();
  const [days, setDays] = useState(7);
  const [selectedNode, setSelectedNode] = useState("all");
  const { data, isLoading, error } = useUsageChartQuery(code, days, true);

  const ranges = [
    { days: 7, label: t("usageChart.oneWeek") },
    { days: 14, label: t("usageChart.twoWeeks") },
    { days: 30, label: t("usageChart.thirtyDays") },
  ];

  const daily = data?.daily_points ?? [];
  const series = data?.series ?? [];
  const nodes = data?.available_nodes ?? [];
  const periodTotalBytes = data?.period_total_bytes ?? 0;
  const trendPercent = data?.trend_percent ?? null;
  const trendDirection = data?.trend_direction ?? null;

  const trendClass =
    trendDirection === "down" ? "text-danger" : trendDirection === "up" ? "text-success" : "text-muted";
  const trendText =
    trendDirection === "down"
      ? t("usageChart.trendDown")
      : trendDirection === "up"
        ? t("usageChart.trendUp")
        : t("usageChart.trendStable");

  const content = (
    <div className="space-y-3">
      <SegmentedControl
        options={ranges.map((r) => ({ value: String(r.days), label: r.label }))}
        value={String(days)}
        onChange={(v) => setDays(Number(v))}
        columns={3}
      />

      {nodes.length > 0 && (
        <div className="relative">
          <select
            value={selectedNode}
            onChange={(e) => setSelectedNode(e.target.value)}
            className="h-11 w-full appearance-none rounded-md border border-border bg-surface px-3.5 pr-9 text-sm text-text outline-none transition-colors focus:border-primary"
          >
            <option value="all">{t("usageChart.allLocations")}</option>
            {nodes.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
          <ChevronDown
            size={16}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted"
          />
        </div>
      )}

      {error && <p className="text-sm text-danger">{(error as Error).message}</p>}
      {isLoading ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : daily.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted">{t("usageChart.noUsage")}</p>
      ) : (
        <>
          <UsageAreaChart daily={daily} series={series} selectedNode={selectedNode} />
          <Card className="p-4">
            {trendPercent != null && trendDirection && (
              <p className={`mb-1 text-sm ${trendClass}`}>
                {trendText}
                {trendDirection !== "stable" && ` · ${trendPercent}%`}
              </p>
            )}
            <p className="text-base font-bold text-text">
              {t("usageChart.totalPeriodUsage")}: {formatBytes(periodTotalBytes, 1)}
            </p>
            <p className="mt-1 text-[11px] text-muted">{t("usageChart.chartHint")}</p>
          </Card>
        </>
      )}
    </div>
  );

  if (embedded) return content;
  return <div>{content}</div>;
}

export interface UsageChartSheetProps {
  open: boolean;
  onClose: () => void;
  code: number;
  username: string;
}

export function UsageChartSheet({ open, onClose, code, username }: UsageChartSheetProps) {
  const { t } = useTranslation();
  return (
    <Sheet open={open} onClose={onClose} title={t("usageChart.title")}>
      <p className="mb-3 text-xs text-muted">
        {username} · {t("usageChart.dailyUsageByLocation")}
      </p>
      {open && <UsageChartPanel code={code} embedded />}
    </Sheet>
  );
}
