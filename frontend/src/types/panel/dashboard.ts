/** Mirrors app/models/panel/dashboard.py */
import type { PanelEnvelope } from "./common";

export interface PanelStats {
  users_total: number;
  users_blocked: number;
  users_today: number;
  wallet_total: number;
  services_total: number;
  services_active: number;
  services_expired: number;
  income_today: number;
  income_month: number;
  pending_tx: number;
  panels_total: number;
  resellers_active: number;
}

export interface PanelDayPoint {
  ts: number;
  revenue: number;
  signups: number;
}

export interface PanelDashboardResponse extends PanelEnvelope {
  stats: PanelStats;
  series: PanelDayPoint[];
  badges: Record<string, number>;
}

export interface PanelMeResponse extends PanelEnvelope {
  user_id: number;
  username: string;
  badges: Record<string, number>;
}
