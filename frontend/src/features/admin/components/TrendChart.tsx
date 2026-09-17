import { useState } from "react";
import { useTranslation } from "react-i18next";

export interface TrendPoint {
  /** Unix seconds at the start of the day. */
  ts: number;
  value: number;
}

export interface TrendChartProps {
  points: TrendPoint[];
  /** Turns a value into the label shown on hover. */
  format: (value: number) => string;
  tone?: "primary" | "accent";
  /** Shown top-right as a running total for the whole period, when given. */
  total?: string;
}

const BAR_TONE: Record<"primary" | "accent", string> = {
  primary: "bg-gradient-to-t from-primary/50 to-primary hover:to-primary-strong",
  accent: "bg-gradient-to-t from-accent/50 to-accent hover:to-accent/90",
};

/** A compact daily bar chart — enough for a 14-day trend, no chart library. */
export function TrendChart({ points, format, tone = "primary", total }: TrendChartProps) {
  const { t, i18n } = useTranslation();
  const [hover, setHover] = useState<number | null>(null);

  const highest = points.length ? Math.max(...points.map((point) => point.value)) : 0;
  const dayFormatter = new Intl.DateTimeFormat(i18n.language === "fa" ? "fa-IR-u-ca-persian" : "en-US", {
    month: "short",
    day: "numeric",
  });

  // A row of stub bars under a made-up peak reads as a broken chart, so a
  // period with nothing in it says so instead.
  if (!points.length || highest <= 0) {
    return <p className="py-8 text-center text-sm text-muted">{t("panel.trendChart.empty")}</p>;
  }

  const first = points[0];
  const last = points[points.length - 1];
  const active = hover === null ? null : points[hover];

  return (
    <div>
      {total !== undefined && (
        <div className="mb-3 flex items-baseline justify-between">
          <span className="text-xs text-muted">{t("panel.trendChart.periodTotal")}</span>
          <span className="text-lg font-bold text-text">{total}</span>
        </div>
      )}

      <div className="flex h-32 items-end gap-1 pt-9" onMouseLeave={() => setHover(null)}>
        {points.map((point, index) => (
          <div key={point.ts} className="relative flex h-full flex-1 items-end">
            {active && hover === index && (
              <div className="pointer-events-none absolute inset-x-0 bottom-full mb-1.5 flex justify-center">
                <div className="whitespace-nowrap rounded-md border border-border bg-surface px-2 py-1 text-center shadow-lg">
                  <p className="text-[11px] font-semibold text-text">{format(active.value)}</p>
                  <p className="text-[10px] text-muted">{dayFormatter.format(new Date(active.ts * 1000))}</p>
                </div>
              </div>
            )}
            <button
              type="button"
              onMouseEnter={() => setHover(index)}
              onFocus={() => setHover(index)}
              onBlur={() => setHover(null)}
              className={`w-full rounded-t transition-colors ${
                point.value > 0 ? BAR_TONE[tone] : "bg-border/60"
              } ${hover === index ? "outline outline-2 outline-offset-1 outline-primary/50" : ""}`}
              style={{ height: `${point.value > 0 ? Math.max(6, (point.value / highest) * 100) : 3}%` }}
              aria-label={`${dayFormatter.format(new Date(point.ts * 1000))}: ${format(point.value)}`}
            />
          </div>
        ))}
      </div>
      <div className="mt-2 flex items-center justify-between text-xs text-muted">
        <span>{first ? dayFormatter.format(new Date(first.ts * 1000)) : ""}</span>
        <span>{last ? dayFormatter.format(new Date(last.ts * 1000)) : ""}</span>
      </div>
    </div>
  );
}
