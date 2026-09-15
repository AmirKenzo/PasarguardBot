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
}

const dayFormatter = new Intl.DateTimeFormat("fa-IR-u-ca-persian", { month: "numeric", day: "numeric" });

/** A compact daily bar chart — enough for a 14-day trend, no chart library. */
export function TrendChart({ points, format, tone = "primary" }: TrendChartProps) {
  const { t } = useTranslation();
  const [hover, setHover] = useState<number | null>(null);

  const highest = points.length ? Math.max(...points.map((point) => point.value)) : 0;

  // A row of stub bars under a made-up peak reads as a broken chart, so a
  // period with nothing in it says so instead.
  if (!points.length || highest <= 0) {
    return (
      <p className="py-8 text-center text-sm text-muted">{t("panel.trendChart.empty")}</p>
    );
  }

  const first = points[0];
  const last = points[points.length - 1];
  const active = hover === null ? null : points[hover];
  const barClass = tone === "primary" ? "bg-primary/35 hover:bg-primary/60" : "bg-accent/35 hover:bg-accent/60";

  return (
    <div>
      <div className="flex h-32 items-end gap-1" onMouseLeave={() => setHover(null)}>
        {points.map((point, index) => (
          <button
            key={point.ts}
            type="button"
            onMouseEnter={() => setHover(index)}
            onFocus={() => setHover(index)}
            className={`flex-1 rounded-t transition-colors ${
              point.value > 0 ? barClass : "bg-border/60"
            } ${hover === index ? "ring-1 ring-primary" : ""}`}
            style={{ height: `${point.value > 0 ? Math.max(6, (point.value / highest) * 100) : 3}%` }}
            aria-label={`${dayFormatter.format(new Date(point.ts * 1000))}: ${format(point.value)}`}
          />
        ))}
      </div>
      <div className="mt-2 flex items-center justify-between text-xs text-muted">
        <span>{first ? dayFormatter.format(new Date(first.ts * 1000)) : ""}</span>
        <span className="font-medium text-text">
          {active
            ? `${dayFormatter.format(new Date(active.ts * 1000))} — ${format(active.value)}`
            : t("panel.trendChart.peak", { value: format(highest) })}
        </span>
        <span>{last ? dayFormatter.format(new Date(last.ts * 1000)) : ""}</span>
      </div>
    </div>
  );
}
