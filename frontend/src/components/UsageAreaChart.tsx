import { useMemo, useState } from "react";
import type { WebAppUsageChartDayItem, WebAppUsageChartSeriesItem } from "../types/webapp";

function formatGb(bytes: number) {
  if (bytes >= 1073741824) return `${(bytes / 1073741824).toFixed(2)} GB`;
  if (bytes >= 1048576) return `${(bytes / 1048576).toFixed(0)} MB`;
  return `${(bytes / 1024).toFixed(0)} KB`;
}

function shortDate(iso: string) {
  const [, m, d] = iso.split("-");
  return `${m}/${d}`;
}

export function UsageAreaChart({
  daily,
  series,
  selectedNode,
}: {
  daily: WebAppUsageChartDayItem[];
  series: WebAppUsageChartSeriesItem[];
  selectedNode: string;
}) {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  const activeSeries = useMemo(() => {
    if (selectedNode === "all") return series;
    return series.filter((s) => s.name === selectedNode);
  }, [series, selectedNode]);

  const labels = daily.map((d) => d.date);
  const width = 360;
  const height = 200;
  const pad = { t: 16, r: 12, b: 32, l: 48 };
  const innerW = width - pad.l - pad.r;
  const innerH = height - pad.t - pad.b;

  const maxY = Math.max(...daily.map((d) => d.bytes), 1);
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((t) => t * maxY);

  const xAt = (i: number) => pad.l + (labels.length <= 1 ? innerW / 2 : (i / (labels.length - 1)) * innerW);
  const yAt = (v: number) => pad.t + innerH - (v / maxY) * innerH;

  const buildSmoothPath = (points: WebAppUsageChartDayItem[]) => {
    if (points.length === 0) return { line: "", area: "" };
    const coords = points.map((p) => {
      const idx = labels.indexOf(p.date);
      return { x: xAt(idx), y: yAt(p.bytes) };
    });
    let line = `M ${coords[0]!.x} ${coords[0]!.y}`;
    for (let i = 1; i < coords.length; i++) {
      const prev = coords[i - 1]!;
      const curr = coords[i]!;
      const cpx = (prev.x + curr.x) / 2;
      line += ` C ${cpx} ${prev.y}, ${cpx} ${curr.y}, ${curr.x} ${curr.y}`;
    }
    const first = coords[0]!;
    const last = coords[coords.length - 1]!;
    const area = `${line} L ${last.x} ${yAt(0)} L ${first.x} ${yAt(0)} Z`;
    return { line, area };
  };

  const hoverDay = hoverIdx != null ? daily[hoverIdx] : null;
  const hoverBreakdown = hoverDay
    ? activeSeries
        .map((s) => {
          const pt = s.points.find((p) => p.date === hoverDay.date);
          return pt && pt.bytes > 0 ? { name: s.name, color: s.color, ...pt } : null;
        })
        .filter(Boolean) as Array<{ name: string; color: string; bytes: number; size_text: string }>
    : [];

  return (
    <div className="relative overflow-hidden rounded-lg border border-border bg-surface p-3 shadow-sm">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgb(var(--c-accent-rgb)/0.08),transparent_55%)]" />
      <svg viewBox={`0 0 ${width} ${height}`} className="relative w-full touch-none">
        <defs>
          {activeSeries.map((s, gi) => (
            <linearGradient key={`g-${gi}`} id={`grad-${gi}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={s.color} stopOpacity={0.55} />
              <stop offset="100%" stopColor={s.color} stopOpacity={0.02} />
            </linearGradient>
          ))}
        </defs>
        {yTicks.map((tick) => (
          <g key={tick}>
            <line
              x1={pad.l}
              x2={width - pad.r}
              y1={yAt(tick)}
              y2={yAt(tick)}
              stroke="rgb(var(--c-border-rgb) / var(--c-border-alpha))"
            />
            <text x={pad.l - 8} y={yAt(tick) + 4} textAnchor="end" className="fill-muted text-[9px]">
              {formatGb(tick)}
            </text>
          </g>
        ))}
        {labels.map((date, i) => (
          <text key={date} x={xAt(i)} y={height - 8} textAnchor="middle" className="fill-muted text-[9px]">
            {shortDate(date)}
          </text>
        ))}
        {activeSeries.map((s, gi) => {
          const { line, area } = buildSmoothPath(s.points);
          return (
            <g key={s.name}>
              <path d={area} fill={`url(#grad-${gi})`} />
              <path d={line} fill="none" stroke={s.color} strokeWidth={2} strokeLinecap="round" />
            </g>
          );
        })}
        {labels.map((_, i) => (
          <rect
            key={i}
            x={xAt(i) - innerW / Math.max(labels.length, 1) / 2}
            y={pad.t}
            width={innerW / Math.max(labels.length, 1)}
            height={innerH}
            fill="transparent"
            onMouseEnter={() => setHoverIdx(i)}
            onMouseLeave={() => setHoverIdx(null)}
            onTouchStart={() => setHoverIdx(i)}
          />
        ))}
        {hoverIdx != null && (
          <>
            <line
              x1={xAt(hoverIdx)}
              x2={xAt(hoverIdx)}
              y1={pad.t}
              y2={pad.t + innerH}
              stroke="rgb(var(--c-text-muted-rgb) / 0.35)"
              strokeDasharray="4 3"
            />
            {activeSeries.map((s) => {
              const pt = s.points.find((p) => p.date === labels[hoverIdx]);
              if (!pt || pt.bytes <= 0) return null;
              const idx = labels.indexOf(pt.date);
              return (
                <circle
                  key={s.name}
                  cx={xAt(idx)}
                  cy={yAt(pt.bytes)}
                  r={4}
                  fill={s.color}
                  stroke="rgb(var(--c-surface-rgb))"
                  strokeWidth={2}
                />
              );
            })}
          </>
        )}
      </svg>

      {hoverDay && (
        <div className="absolute left-3 top-3 max-w-[230px] rounded-md border border-border bg-surface/95 p-3 shadow-lg backdrop-blur-md">
          <p className="text-xs font-semibold text-text">{hoverDay.label}</p>
          <p className="mt-0.5 text-base font-bold text-text">{hoverDay.size_text}</p>
          <div className="mt-2 max-h-28 space-y-1.5 overflow-y-auto">
            {hoverBreakdown.map((node) => (
              <div key={node.name} className="flex items-center justify-between gap-2 text-[11px]">
                <span className="flex min-w-0 items-center gap-1.5 text-text">
                  <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: node.color }} />
                  <span className="truncate">{node.name}</span>
                </span>
                <span className="shrink-0 text-muted">{node.size_text}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
