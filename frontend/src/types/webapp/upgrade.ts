/** Mirrors app/models/webapp/upgrade.py */
import type { WebAppAuthRequest } from "./common";

export interface TimePlanItem {
  id: number;
  duration_days: number;
  price: number;
}

export interface WebAppExtendTimeOptionsRequest extends WebAppAuthRequest {
  code: number;
}

export interface WebAppExtendTimeOptionsResponse {
  ok: boolean;
  service_code?: string | null;
  panel_name?: string | null;
  plans: TimePlanItem[];
  error?: string | null;
}

export interface WebAppExtendTimeConfirmRequest extends WebAppAuthRequest {
  code: number;
  plan_id: number;
}

export interface WebAppExtendTimeConfirmResponse {
  ok: boolean;
  new_balance?: number | null;
  new_expiration_timestamp?: number | null;
  added_days?: number | null;
  amount_paid?: number | null;
  config_name?: string | null;
  error?: string | null;
}

export interface VolumePlanItem {
  id: number;
  storage_gb: number;
  price: number;
}

export interface WebAppExtraVolumeOptionsRequest extends WebAppAuthRequest {
  code: number;
}

export interface WebAppExtraVolumeOptionsResponse {
  ok: boolean;
  service_code?: string | null;
  panel_name?: string | null;
  plans: VolumePlanItem[];
  error?: string | null;
}

export interface WebAppExtraVolumeConfirmRequest extends WebAppAuthRequest {
  code: number;
  plan_id: number;
}

export interface WebAppExtraVolumeConfirmResponse {
  ok: boolean;
  new_balance?: number | null;
  new_total_traffic_bytes?: number | null;
  added_bytes?: number | null;
  amount_paid?: number | null;
  config_name?: string | null;
  error?: string | null;
}

export interface WebAppTransferConfigRequest extends WebAppAuthRequest {
  code: number;
  target_user_id: number;
}

export interface WebAppTransferConfigResponse {
  ok: boolean;
  target_user_id?: number | null;
  error?: string | null;
}
