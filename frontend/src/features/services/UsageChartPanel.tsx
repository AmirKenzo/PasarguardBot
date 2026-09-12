import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { UsageAreaChart } from "../../components/UsageAreaChart";
import { Card } from "../../components/ui/Card";
import { Sheet } from "../../components/ui/Sheet";
import { Spinner } from "../../components/ui/Spinner";
import { SegmentedControl } from "../../components/ui/Select";
import { useUsageChartQuery } from "../../queries/useServices";

const RANGES = [
  { days: 7, label: "۱ هفته" },
  { days: 14, label: "۲ هفته" },
  { days: 30, label: "۳۰ روز" },
] as const;

export interface UsageChartPanelProps {
  code: number;
  embedded?: boolean;
}

export function UsageChartPanel({ code, embedded = false }: UsageChartPanelProps) {
  const [days, setDays] = useState(7);
  const [selectedNode, setSelectedNode] = useState("all");
  const { data, isLoading, error } = useUsageChartQuery(code, days, true);

  const daily = data?.daily_points ?? [];
  const series = data?.series ?? [];
  const nodes = data?.available_nodes ?? [];
  const periodTotal = data?.period_total_text ?? "";
  const trendPercent = data?.trend_percent ?? null;
  const trendLabel = data?.trend_label ?? null;

  const trendClass =
    trendLabel === "کاهشی" ? "text-danger" : trendLabel === "افزایشی" ? "text-success" : "text-muted";

  const content = (
    <div className="space-y-3">
      <SegmentedControl
        options={RANGES.map((r) => ({ value: String(r.days), label: r.label }))}
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
            <option value="all">همه لوکیشن‌ها</option>
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
        <p className="py-8 text-center text-sm text-muted">در این بازه مصرفی ثبت نشده</p>
      ) : (
        <>
          <UsageAreaChart daily={daily} series={series} selectedNode={selectedNode} />
          <Card className="p-4">
            {trendPercent != null && trendLabel && (
              <p className={`mb-1 text-sm ${trendClass}`}>
                روند {trendLabel === "کاهشی" ? "نزولی" : trendLabel === "افزایشی" ? "صعودی" : "ثابت"}
                {trendLabel !== "ثابت" && ` · ${trendPercent}%`}
              </p>
            )}
            <p className="text-base font-bold text-text">مصرف کل بازه: {periodTotal}</p>
            <p className="mt-1 text-[11px] text-muted">انگشت را روی نمودار نگه دار برای جزئیات</p>
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
  return (
    <Sheet open={open} onClose={onClose} title="نمودار مصرف">
      <p className="mb-3 text-xs text-muted">{username} · مصرف روزانه بر اساس لوکیشن</p>
      {open && <UsageChartPanel code={code} embedded />}
    </Sheet>
  );
}
