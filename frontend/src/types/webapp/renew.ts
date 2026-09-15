/** Mirrors app/models/webapp/renew.py */
import type { WebAppAuthRequest } from "./common";

export interface RenewPlanItem {
  id: number;
  storage: number;
  duration: number;
  price: number;
  plan_type: string;
  data_limit_reset_strategy: string;
  ip_limit: number;
}

export interface WebAppRenewOptionsRequest extends WebAppAuthRequest {
  code: number;
}

export interface WebAppRenewOptionsResponse {
  ok: boolean;
  service_code?: string | null;
  panel_name?: string | null;
  is_fair_usage: boolean;
  durations?: number[] | null;
  plans?: RenewPlanItem[] | null;
  error?: string | null;
}

export interface WebAppRenewConfirmRequest extends WebAppAuthRequest {
  code: number;
  plan_id: number;
  discount_code?: string | null;
}

export interface WebAppRenewConfirmResponse {
  ok: boolean;
  message?: string | null;
  new_balance?: number | null;
  new_volume_bytes?: number | null;
  amount_paid?: number | null;
  config_name?: string | null;
  error?: string | null;
}
