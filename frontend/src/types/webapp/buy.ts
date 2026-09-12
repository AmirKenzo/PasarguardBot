/** Mirrors app/models/webapp/buy.py */
import type { WebAppAuthRequest } from "./common";

export interface WebAppBuyPanelItem {
  code: number;
  name: string;
  display_mode: string;
  durations: number[];
}

export type WebAppBuyOptionsRequest = WebAppAuthRequest;

export interface WebAppBuyOptionsResponse {
  ok: boolean;
  single_panel_buy_mode: boolean;
  panels: WebAppBuyPanelItem[];
  error?: string | null;
}

export interface WebAppBuyPlanItem {
  id: number;
  storage: number;
  duration: number;
  price: number;
  plan_name: string;
  plan_type: string;
  data_limit_reset_strategy: string;
  ip_limit: number;
}

export interface WebAppBuyPlansRequest extends WebAppAuthRequest {
  panel_code: number;
  duration?: number | null;
}

export interface WebAppBuyPlansResponse {
  ok: boolean;
  panel?: WebAppBuyPanelItem | null;
  durations: number[];
  duration_groups: Record<string, number[]>;
  plans: WebAppBuyPlanItem[];
  error?: string | null;
}

export interface WebAppBuyUsernameRequest extends WebAppAuthRequest {
  panel_code: number;
}

export interface WebAppBuyUsernameResponse {
  ok: boolean;
  username?: string | null;
  error?: string | null;
}

export interface WebAppBuyPreviewRequest extends WebAppAuthRequest {
  panel_code: number;
  plan_id: number;
  username: string;
  discount_code?: string | null;
}

export interface WebAppBuyPreviewResponse {
  ok: boolean;
  panel_name?: string | null;
  plan?: WebAppBuyPlanItem | null;
  username?: string | null;
  base_price?: number | null;
  final_price?: number | null;
  discount_percent: number;
  balance?: number | null;
  balance_after?: number | null;
  can_pay: boolean;
  locations: string[];
  error?: string | null;
}

export type WebAppBuyConfirmRequest = WebAppBuyPreviewRequest;

export interface WebAppBuyConfirmResponse {
  ok: boolean;
  message?: string | null;
  service_code?: number | null;
  username?: string | null;
  panel_name?: string | null;
  volume?: string | null;
  duration?: number | null;
  ip_limit_text?: string | null;
  subscription_url?: string | null;
  subscription_links_text?: string | null;
  single_config_links_text?: string | null;
  amount_paid?: number | null;
  new_balance?: number | null;
  creation_time_ms?: number | null;
  error?: string | null;
}
