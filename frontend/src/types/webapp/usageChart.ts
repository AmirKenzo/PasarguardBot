/** Mirrors app/models/webapp/usage_chart.py */
import type { WebAppAuthRequest } from "./common";

export interface WebAppUsageChartDayItem {
  date: string;
  bytes: number;
}

export interface WebAppUsageChartSeriesItem {
  name: string;
  color: string;
  points: WebAppUsageChartDayItem[];
}

export interface WebAppUsageChartNodeItem {
  name: string;
  bytes: number;
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
  trend_direction?: "up" | "down" | "stable" | null;
  period_total_bytes?: number | null;
  avg_daily_bytes?: number | null;
  peak_date?: string | null;
  peak_value_bytes?: number | null;
  day_total_bytes?: number | null;
  nodes: WebAppUsageChartNodeItem[];
  error?: string | null;
}
