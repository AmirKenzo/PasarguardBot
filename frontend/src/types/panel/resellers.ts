/** Mirrors app/models/panel/resellers.py */
import type { PagedRequest, PageMeta, PanelAuthRequest, PanelEnvelope, PanelOption } from "./common";

export const RESELLER_STATUSES = ["active", "paused", "suspended", "usage_capped", "admin_paused", "expired"] as const;

// --------------------------------------------------------------------------- //
//  Overview                                                                     //
// --------------------------------------------------------------------------- //

/** `payg` is hourly/usage billing, `sales` is purchases, renewals and capacity. */
export interface PanelResellerRevenue {
  payg: number;
  sales: number;
  total: number;
}

export interface PanelResellerDayPoint {
  ts: number;
  payg: number;
  sales: number;
}

export interface PanelResellerRunwayRow {
  telegram_id: number;
  balance: number;
  burn_per_hour: number;
  hours_left?: number | null;
  accounts: string[];
}

export interface PanelResellerExpiringRow {
  code: number;
  telegram_id: number;
  username: string;
  status: string;
  expiration_time: number;
  /** When an expired account is deleted from the panel. */
  purge_at?: number | null;
}

export interface PanelResellerEventRow {
  id: number;
  kind: string;
  title: string;
  account_code?: number | null;
  telegram_id?: number | null;
  actor_id?: number | null;
  actor_role?: string | null;
  data: Record<string, unknown>;
  created_at: number;
}

export interface PanelResellerOverviewResponse extends PanelEnvelope {
  sale_enabled: boolean;
  total: number;
  by_status: Record<string, number>;
  by_mode: Record<string, number>;
  burn_per_hour: number;
  revenue_today: PanelResellerRevenue;
  revenue_7d: PanelResellerRevenue;
  revenue_30d: PanelResellerRevenue;
  series: PanelResellerDayPoint[];
  low_runway_hours: number;
  at_risk: PanelResellerRunwayRow[];
  expiring: PanelResellerExpiringRow[];
  recent_events: PanelResellerEventRow[];
}

// --------------------------------------------------------------------------- //
//  Accounts                                                                     //
// --------------------------------------------------------------------------- //

export interface PanelResellerRow {
  code: number;
  telegram_id?: number | null;
  username?: string | null;
  panel_code?: number | null;
  panel?: string | null;
  panel_admin_id?: number | null;
  plan_id?: number | null;
  pricing_mode: string;
  purchased_volume?: number | null;
  data_limit?: number | null;
  usage_cap_bytes?: number | null;
  max_users?: number | null;
  /** User slots bought above the plan's limit. */
  extra_users?: number | null;
  createtime?: number | null;
  expiration_time?: number | null;
  status: string;
}

export interface PanelResellersRequest extends PagedRequest {
  q?: string;
  status?: string;
  panel_code?: number | null;
  pricing_mode?: string;
}

export interface PanelResellersResponse extends PanelEnvelope {
  resellers: PanelResellerRow[];
  panels: PanelOption[];
  statuses: string[];
  pricing_modes: string[];
  meta: PageMeta;
}

/** One charge: `used_bytes` (usage) or `billed_minutes` (hourly) × `unit_price` = `billed_amount`. */
export interface PanelResellerSnapshotRow {
  id: number;
  account_code?: number | null;
  username?: string | null;
  telegram_id?: number | null;
  /** hourly | usage */
  kind: string;
  /** Panel's cumulative traffic counter at charge time. */
  used_traffic: number;
  /** Traffic used in the charged period. */
  used_bytes?: number | null;
  billed_amount: number;
  billed_minutes?: number | null;
  /** Rate per GB (usage) or per hour (hourly). */
  unit_price?: number | null;
  /** Rate rebuilt from amount ÷ usage for rows written before rates were stored. */
  rate_estimated: boolean;
  period_start?: number | null;
  snapshot_at?: number | null;
  /** Charged while the wallet was short; left the balance negative. */
  is_debt: boolean;
}

export interface PanelResellerLive {
  used_traffic: number;
  data_limit: number;
  total_users: number;
  admin_status: string;
  login_url: string;
}

export interface PanelResellerPlanBrief {
  id: number;
  pricing_mode: string;
  name?: string | null;
  /** Package price (fixed/unlimited) or price per GB / hour. */
  rate: number;
  enable: boolean;
  duration: number;
  data_limit_gb: number;
  max_users: number;
}

/** Mirrors app/services/reseller/plan_rules.plan_features. */
export interface PanelResellerPlanFeatures {
  mode: string;
  renewable: boolean;
  expires: boolean;
  unlimited_volume: boolean;
  usage_cap: boolean;
  needs_wallet: boolean;
  extra_day_price: number;
  extra_gb_price: number;
  extra_user_price: number;
}

export interface PanelResellerDetailRequest extends PanelAuthRequest {
  code: number;
}

export interface PanelResellerDetailResponse extends PanelEnvelope {
  reseller?: PanelResellerRow | null;
  plan?: PanelResellerPlanBrief | null;
  plan_features?: PanelResellerPlanFeatures | null;
  live?: PanelResellerLive | null;
  live_error?: string | null;
  balance?: number | null;
  billed_total?: number | null;
  runway_hours?: number | null;
  grace_days_left?: number | null;
  /** Days an expired account is kept before it is purged. */
  grace_days?: number | null;
  actions: string[];
  /** Only the account's own plan: renewal never switches plans. */
  renew_plans: PanelResellerPlanBrief[];
  /** Other plans of the same panel and type the admin can move the account to. */
  change_plans?: PanelResellerPlanBrief[];
  snapshots: PanelResellerSnapshotRow[];
  events: PanelResellerEventRow[];
  statuses: string[];
}

export interface PanelResellerCodeRequest extends PanelAuthRequest {
  code: number;
}

export type PanelResellerDeleteRequest = PanelResellerCodeRequest;

export interface PanelResellerRenewRequest extends PanelAuthRequest {
  code: number;
  plan_id: number;
}

export interface PanelResellerExtendRequest extends PanelAuthRequest {
  code: number;
  days: number;
}

export interface PanelResellerUsageCapRequest extends PanelAuthRequest {
  code: number;
  /** Null or 0 removes the cap. */
  usage_cap_gb: number | null;
}

export interface PanelResellerMaxUsersRequest extends PanelAuthRequest {
  code: number;
  max_users: number;
}

/** Exactly one of `set_gb` / `add_gb`. */
export interface PanelResellerDataLimitRequest extends PanelAuthRequest {
  code: number;
  set_gb?: number | null;
  add_gb?: number | null;
}

export interface PanelResellerChangePlanRequest extends PanelAuthRequest {
  code: number;
  plan_id: number;
}

export interface PanelResellerPasswordResponse extends PanelEnvelope {
  message?: string | null;
  password?: string | null;
}

// --------------------------------------------------------------------------- //
//  Ledger and events                                                            //
// --------------------------------------------------------------------------- //

export interface PanelResellerLedgerRequest extends PagedRequest {
  account_code?: number | null;
  telegram_id?: number | null;
  since?: number | null;
  until?: number | null;
}

export interface PanelResellerLedgerResponse extends PanelEnvelope {
  rows: PanelResellerSnapshotRow[];
  total_billed: number;
  meta: PageMeta;
}

export interface PanelResellerEventsRequest extends PagedRequest {
  account_code?: number | null;
  telegram_id?: number | null;
  kinds?: string[];
}

export interface PanelResellerEventsResponse extends PanelEnvelope {
  events: PanelResellerEventRow[];
  kinds: string[];
  meta: PageMeta;
}

// --------------------------------------------------------------------------- //
//  Settings                                                                     //
// --------------------------------------------------------------------------- //

export interface PanelResellerGlobalSettings {
  sale_mode: boolean;
  min_wallet_balance: number;
  grace_days: number;
  low_balance_hours: number;
  usage_debt: boolean;
}

export interface PanelResellerButtons {
  credentials: boolean;
  change_password: boolean;
  toggle_status: boolean;
  usage_report: boolean;
  usage_cap: boolean;
  buy_user_capacity: boolean;
  extra_days: boolean;
  extra_volume: boolean;
  delete: boolean;
}

export interface PanelResellerPanelSettings {
  code: number;
  name: string;
  enable: boolean;
  sale_enabled: boolean;
  /** Ignored by the server: the extra-user price is set on each plan now. */
  capacity_enabled: boolean;
  /** Ignored by the server: the extra-user price is set on each plan now. */
  capacity_price_per_user: number;
  buttons: PanelResellerButtons;
}

export interface PanelResellerSettingsResponse extends PanelEnvelope {
  settings: PanelResellerGlobalSettings;
  panels: PanelResellerPanelSettings[];
}

export interface PanelResellerSettingsSaveRequest extends PanelAuthRequest {
  settings?: PanelResellerGlobalSettings | null;
  panels?: PanelResellerPanelSettings[] | null;
}

// --------------------------------------------------------------------------- //
//  Plans                                                                        //
// --------------------------------------------------------------------------- //

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
  data_limit_gb: number;
  max_users: number;
  duration: number;
  role_id: number;
  role_name?: string | null;
  enable: boolean;
  display_button_text?: string | null;
  button_style?: string | null;
  button_icon?: number | null;
  linked_accounts: number;
  addon_day_price: number;
  addon_gb_price: number;
  addon_user_price: number;
  features?: PanelResellerPlanFeatures;
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
  /** Null keeps the stored value; 0 is unlimited. */
  data_limit_gb?: number | null;
  max_users?: number;
  duration?: number;
  role_id: number;
  role_name?: string;
  enable?: boolean;
  display_button_text?: string;
  button_style?: string;
  button_icon?: string;
  /** Message linked pay-as-you-go resellers when the rate changes. */
  notify_resellers?: boolean;
  /** Add-on prices per unit; 0 = off. Left out on an edit, the stored price is kept. */
  addon_day_price?: number;
  addon_gb_price?: number;
  addon_user_price?: number;
}

export interface PanelResellerPlanDeleteRequest extends PanelAuthRequest {
  plan_id: number;
}

export interface PanelResellerRolesRequest extends PanelAuthRequest {
  panel_code: number;
}

export interface PanelResellerRole {
  id: number;
  name: string;
}

export interface PanelResellerRolesResponse extends PanelEnvelope {
  roles: PanelResellerRole[];
}
