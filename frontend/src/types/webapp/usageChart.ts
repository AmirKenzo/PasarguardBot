/** Mirrors app/models/webapp/usage_chart.py */
import type { WebAppAuthRequest } from "./common";

export interface WebAppUsageChartDayItem {
  date: string;
  label: string;
  bytes: number;
  size_text: string;
}

export interface WebAppUsageChartSeriesItem {
  name: string;
  color: string;
  points: WebAppUsageChartDayItem[];
}

export interface WebAppUsageChartNodeItem {
  name: string;
  bytes: number;
  size_text: string;
  percent: number;
}

export interface WebAppUsageChartRequest extends WebAppAuthRequest {
  code: number;
  days?: number;
  page?: number;
  day?: string | null;
}

export interface WebAppUsageChartResponse {
  ok: boolean;
  mode: "chart" | "day";
  days: number;
  page: number;
  total_pages: number;
  daily_points: WebAppUsageChartDayItem[];
  series: WebAppUsageChartSeriesItem[];
  available_nodes: string[];
  trend_percent?: number | null;
  trend_label?: string | null;
  period_total_text?: string | null;
  avg_daily_text?: string | null;
  peak_label?: string | null;
  peak_value_text?: string | null;
  page_total_text?: string | null;
  day_label?: string | null;
  day_jalali?: string | null;
  day_total_text?: string | null;
  nodes: WebAppUsageChartNodeItem[];
  error?: string | null;
}
