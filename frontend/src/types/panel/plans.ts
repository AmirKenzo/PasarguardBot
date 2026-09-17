/** Mirrors app/models/panel/plans.py */
import type { PagedRequest, PanelAuthRequest, PanelEnvelope, PageMeta } from "./common";

export const PLAN_TYPES = ["volume", "fair_usage"] as const;
export const RESET_STRATEGIES = ["no_reset", "day", "week", "month", "year"] as const;
export const BUTTON_STYLE_VALUES = ["", "primary", "success", "danger"] as const;
export const PLAN_SORT_VALUES = [
  "newest",
  "oldest",
  "price_asc",
  "price_desc",
  "volume_asc",
  "volume_desc",
  "duration_asc",
  "duration_desc",
] as const;

export interface PanelPlanRow {
  id: number;
  panel_code: number;
  panel?: string | null;
  storage: number;
  duration: number;
  price: number;
  plan_type: string;
  data_limit_reset_strategy: string;
  ip_limit: number;
  display_button_text?: string | null;
  button_style?: string | null;
  button_icon?: number | null;
}

export interface PanelPlansRequest extends PagedRequest {
  /** Panel code, or empty for all. */
  panel?: string;
  /** newest | oldest | price_asc | price_desc | volume_asc | volume_desc | duration_asc | duration_desc */
  sort?: string;
}

export interface PanelPlansResponse extends PanelEnvelope {
  plans: PanelPlanRow[];
  meta: PageMeta;
  plan_types: string[];
  reset_strategies: string[];
  button_styles: string[];
}

export interface PanelPlanSaveRequest extends PanelAuthRequest {
  plan_id?: number | null;
  panel_code: number;
  /** Gigabytes, zero meaning unlimited. */
  storage?: number;
  duration: number;
  price: number;
  plan_type?: string;
  data_limit_reset_strategy?: string;
  ip_limit?: number;
  display_button_text?: string;
  button_style?: string;
  /** Premium emoji id, or empty. */
  button_icon?: string;
}

export interface PanelPlanDeleteRequest extends PanelAuthRequest {
  plan_id: number;
}
