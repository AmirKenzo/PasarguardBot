/** Mirrors app/models/panel/resellers.py */
import type { PagedRequest, PageMeta, PanelAuthRequest, PanelEnvelope, PanelOption } from "./common";

export const RESELLER_STATUSES = ["active", "suspended", "expired"] as const;

export interface PanelResellerRow {
  code: number;
  telegram_id?: number | null;
  username?: string | null;
  panel_code?: number | null;
  panel?: string | null;
  pricing_mode: string;
  purchased_volume?: number | null;
  usage_cap_bytes?: number | null;
  max_users?: number | null;
  createtime?: number | null;
  expiration_time?: number | null;
  status: string;
}

export interface PanelResellersRequest extends PagedRequest {
  q?: string;
  /** empty | active | suspended | expired */
  status?: string;
}

export interface PanelResellersResponse extends PanelEnvelope {
  resellers: PanelResellerRow[];
  panels: PanelOption[];
  statuses: string[];
  meta: PageMeta;
}

export interface PanelResellerSnapshotRow {
  id: number;
  used_traffic: number;
  billed_amount: number;
  snapshot_at?: number | null;
}

export interface PanelResellerDetailRequest extends PanelAuthRequest {
  code: number;
}

export interface PanelResellerDetailResponse extends PanelEnvelope {
  reseller?: PanelResellerRow | null;
  snapshots: PanelResellerSnapshotRow[];
  statuses: string[];
}

export interface PanelResellerUpdateRequest extends PanelAuthRequest {
  code: number;
  status?: string;
  /** Null removes the cap. */
  usage_cap_gb?: number | null;
  max_users?: number;
  /** Days added to the current expiry. */
  extend_days?: number;
}

export interface PanelResellerDeleteRequest extends PanelAuthRequest {
  code: number;
}

export interface PanelResellerPlanRow {
  id: number;
  panel_code: number;
  panel?: string | null;
  pricing_mode: string;
  price: number;
  unit_price: number;
  min_volume: number;
  max_volume: number;
  volume_step: number;
  max_users: number;
  duration: number;
  role_id: number;
  role_name?: string | null;
  enable: boolean;
  display_button_text?: string | null;
  button_style?: string | null;
  button_icon?: number | null;
}

export interface PanelResellerPlansResponse extends PanelEnvelope {
  plans: PanelResellerPlanRow[];
  panels: PanelOption[];
  pricing_modes: string[];
  button_styles: string[];
}

export interface PanelResellerPlanSaveRequest extends PanelAuthRequest {
  plan_id?: number | null;
  panel_code: number;
  pricing_mode?: string;
  price?: number;
  unit_price?: number;
  min_volume?: number;
  max_volume?: number;
  volume_step?: number;
  max_users?: number;
  duration?: number;
  role_id: number;
  role_name?: string;
  enable?: boolean;
  display_button_text?: string;
  button_style?: string;
  button_icon?: string;
}

export interface PanelResellerPlanDeleteRequest extends PanelAuthRequest {
  plan_id: number;
}
