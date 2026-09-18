/** Mirrors app/models/panel/reports.py */
import type { PagedRequest, PageMeta, PanelAuthRequest, PanelEnvelope } from "./common";

export const REPORT_PERIODS = ["today", "3d", "week", "month", "quarter", "year", "all"] as const;

export interface PanelRankRow {
  rank: number;
  user_id?: number | null;
  amount: number;
  count: number;
}

export interface PanelReportTotals {
  new_users: number;
  services_sold: number;
  test_services: number;
  manual_approved_sum: number;
  auto_approved_sum: number;
  pending_sum: number;
  pending_count: number;
}

export interface PanelReportsRequest extends PanelAuthRequest {
  /** today | 3d | week | month | quarter | year | all */
  period?: string;
}

export interface PanelReportsResponse extends PanelEnvelope {
  period: string;
  period_start: number;
  periods: string[];
  totals: PanelReportTotals;
  top_recharge: PanelRankRow[];
  top_spenders: PanelRankRow[];
  top_service_counts: PanelRankRow[];
}

export interface PanelAuditRow {
  id: number;
  actor_id?: number | null;
  actor_username?: string | null;
  action: string;
  target_type?: string | null;
  target_id?: string | null;
  detail?: Record<string, unknown> | null;
  ip?: string | null;
  created_at?: number | null;
}

export interface PanelAuditRequest extends PagedRequest {
  action?: string;
  actor_id?: number | null;
}

export interface PanelAuditResponse extends PanelEnvelope {
  entries: PanelAuditRow[];
  actions: string[];
  meta: PageMeta;
}
