/** Mirrors app/models/webapp/reseller.py */
import type { WebAppAuthRequest } from "./common";

export interface WebAppResellerEnvelope {
  ok: boolean;
  error?: string | null;
}

// --------------------------------------------------------------------------- //
//  Buy                                                                          //
// --------------------------------------------------------------------------- //

/** What a buyer of the plan gets; an add-on price of 0 means the add-on is off (plan or panel toggle). */
export interface ResellerPlanFeatures {
  renewable: boolean;
  expires: boolean;
  unlimited_volume: boolean;
  usage_cap: boolean;
  needs_wallet: boolean;
  extra_day_price: number;
  /** Price of one extra GB. */
  extra_gb_price: number;
  extra_user_price: number;
}

export interface ResellerPlanItem {
  id: number;
  pricing_mode: string;
  name?: string | null;
  price: number;
  unit_price: number;
  min_volume: number;
  max_volume: number;
  volume_step: number;
  data_limit_bytes: number;
  max_users: number;
  duration_days: number;
  needs_volume: boolean;
  needs_wallet: boolean;
  /** Optional for older servers. */
  features?: ResellerPlanFeatures;
}

export interface ResellerPanelItem {
  code: number;
  name: string;
  plans: ResellerPlanItem[];
}

export interface WebAppResellerBuyOptionsResponse extends WebAppResellerEnvelope {
  /** False when reseller sales are off or nothing is on sale; the buy card is hidden. */
  enabled: boolean;
  min_wallet_balance: number;
  /** Days an expired reseller is kept before it is purged. */
  grace_days?: number;
  balance: number;
  panels: ResellerPanelItem[];
}

export interface WebAppResellerUsernameRequest extends WebAppAuthRequest {
  panel_code: number;
}

export interface WebAppResellerUsernameResponse extends WebAppResellerEnvelope {
  username?: string | null;
}

export interface WebAppResellerBuyRequest extends WebAppAuthRequest {
  panel_code: number;
  plan_id: number;
  username: string;
  volume?: number | null;
  discount_code?: string | null;
}

export interface WebAppResellerBuyPreviewResponse extends WebAppResellerEnvelope {
  panel_name?: string | null;
  plan?: ResellerPlanItem | null;
  username?: string | null;
  volume?: number | null;
  base_price: number;
  final_price: number;
  discount_percent: number;
  balance: number;
  balance_after: number;
  can_pay: boolean;
  wallet_error?: string | null;
}

export interface WebAppResellerBuyConfirmResponse extends WebAppResellerEnvelope {
  account_code?: number | null;
  panel_url?: string | null;
  username?: string | null;
  password?: string | null;
  amount_paid: number;
  new_balance?: number | null;
}

// --------------------------------------------------------------------------- //
//  Accounts                                                                     //
// --------------------------------------------------------------------------- //

export interface ResellerAccountItem {
  code: number;
  username: string;
  panel_name?: string | null;
  pricing_mode: string;
  status: string;
  expiration_timestamp?: number | null;
  max_users: number;
  created_timestamp?: number | null;
  extra_users?: number;
}

export interface WebAppResellerAccountsResponse extends WebAppResellerEnvelope {
  accounts: ResellerAccountItem[];
  balance: number;
  burn_per_hour: number;
  runway_hours?: number | null;
  can_buy: boolean;
}

export interface WebAppResellerCodeRequest extends WebAppAuthRequest {
  code: number;
}

export interface ResellerRenewPlanItem {
  id: number;
  name?: string | null;
  price: number;
  data_limit_bytes: number;
  duration_days: number;
  pricing_mode?: string | null;
  max_users?: number;
  /** False when the plan is off sale for new buyers; the owner can still renew it. */
  enabled?: boolean;
}

export interface ResellerEventItem {
  id: number;
  kind: string;
  title: string;
  data: Record<string, unknown>;
  created_at: number;
}

export interface WebAppResellerAccountResponse extends WebAppResellerEnvelope {
  account?: ResellerAccountItem | null;
  panel_url?: string | null;
  actions: string[];
  admin_locked: boolean;
  /** False when the panel could not be reached. */
  live: boolean;
  used_traffic_bytes: number;
  data_limit_bytes: number;
  total_users: number;
  usage_cap_bytes?: number | null;
  purchased_volume?: number | null;
  rate: number;
  balance?: number | null;
  billed_total?: number | null;
  runway_hours?: number | null;
  grace_days_left?: number | null;
  /** Only the account's own plan; renewal never switches plans. */
  renew_plans: ResellerRenewPlanItem[];
  capacity_price_per_user: number;
  capacity_presets: number[];
  events: ResellerEventItem[];
  plan?: ResellerPlanItem | null;
  features?: ResellerPlanFeatures | null;
  /** User limit of the plan itself; 0 = unlimited. */
  plan_max_users?: number;
  /** User slots bought on top of the plan limit. */
  extra_users?: number;
  grace_days?: number;
  min_wallet_balance?: number;
  addon_presets?: Partial<Record<ResellerAddonKind, number[]>>;
  addon_max_quantity?: Partial<Record<ResellerAddonKind, number>>;
}

export interface WebAppResellerPasswordResponse extends WebAppResellerEnvelope {
  password?: string | null;
  message?: string | null;
}

export interface WebAppResellerActionResponse extends WebAppResellerEnvelope {
  message?: string | null;
  new_balance?: number | null;
}

export interface WebAppResellerRenewRequest extends WebAppAuthRequest {
  code: number;
  plan_id: number;
  discount_code?: string | null;
}

export interface WebAppResellerRenewPreviewResponse extends WebAppResellerEnvelope {
  plan?: ResellerRenewPlanItem | null;
  base_price: number;
  final_price: number;
  discount_percent: number;
  balance: number;
  can_pay: boolean;
  balance_after?: number;
  expiry_before?: number | null;
  expiry_after?: number | null;
  /** Bytes; 0 = unlimited. */
  data_limit_before?: number;
  data_limit_after?: number;
  /** Unchanged by renewal; 0 = unlimited. */
  max_users?: number;
}

export interface WebAppResellerUsageCapRequest extends WebAppAuthRequest {
  code: number;
  /** Null or 0 removes the cap. */
  usage_cap_gb: number | null;
}

export interface WebAppResellerCapacityRequest extends WebAppAuthRequest {
  code: number;
  quantity: number;
}

export interface WebAppResellerCapacityPreviewResponse extends WebAppResellerEnvelope {
  price_per_user: number;
  total_price: number;
  limit_before: number;
  limit_after: number;
  balance: number;
  can_pay: boolean;
}

export type ResellerAddonKind = "extra_days" | "extra_volume" | "buy_user_capacity";

export interface WebAppResellerAddonRequest extends WebAppAuthRequest {
  code: number;
  addon: ResellerAddonKind;
  /** Days, GB or user slots depending on `addon`. */
  quantity: number;
}

/** `before`/`after`: expiry timestamp (days), bytes (volume) or user count (users). */
export interface WebAppResellerAddonPreviewResponse extends WebAppResellerEnvelope {
  addon?: string | null;
  quantity: number;
  unit_price: number;
  total: number;
  before: number;
  after: number;
  balance: number;
  balance_after: number;
  can_pay: boolean;
}

export interface WebAppResellerPageRequest extends WebAppAuthRequest {
  code: number;
  page?: number;
  limit?: number;
}

/** `used_bytes` (usage) or `billed_minutes` (hourly) × `unit_price` = `amount`. */
export interface ResellerUsageRow {
  snapshot_at: number;
  period_start?: number | null;
  /** hourly | usage */
  kind: string;
  used_bytes: number;
  billed_minutes?: number | null;
  unit_price?: number | null;
  rate_estimated: boolean;
  amount: number;
  is_debt: boolean;
}

export interface WebAppResellerUsageResponse extends WebAppResellerEnvelope {
  rows: ResellerUsageRow[];
  total_billed: number;
  has_more: boolean;
}

export interface WebAppResellerEventsResponse extends WebAppResellerEnvelope {
  events: ResellerEventItem[];
  total: number;
}
