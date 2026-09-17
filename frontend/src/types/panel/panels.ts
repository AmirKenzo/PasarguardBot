/** Mirrors app/models/panel/panels.py */
import type { PanelAuthRequest, PanelEnvelope } from "./common";

export const AUTH_TYPES = ["password", "api_key"] as const;

export interface PanelRow {
  code: number;
  name: string;
  base_url: string;
  tunnel_url?: string | null;
  username?: string | null;
  auth_type: string;
  enable: boolean;
  test_enabled: boolean;
  test_volume_gb: number;
  test_duration_days: number;
}

export interface PanelListResponse extends PanelEnvelope {
  panels: PanelRow[];
  auth_types: string[];
}

/** Creates when `code` is null, otherwise updates that panel.
 *  On update an empty `secret` keeps the stored credential. */
export interface PanelSaveRequest extends PanelAuthRequest {
  code?: number | null;
  name: string;
  base_url: string;
  tunnel_url?: string;
  auth_type?: string;
  username?: string;
  secret?: string;
  enable?: boolean;
  test_enabled?: boolean;
  test_volume_gb?: number;
  test_duration_days?: number;
}

export interface PanelCodeRequest extends PanelAuthRequest {
  code: number;
}

export interface PanelTestResponse extends PanelEnvelope {
  message?: string | null;
  latency_ms?: number | null;
}

export const BUTTON_STYLES = ["primary", "success", "danger", ""] as const;

export interface PanelButtonSettings {
  time: boolean;
  volume: boolean;
  renew: boolean;
  change_subscription: boolean;
  other_links: boolean;
  change_link: boolean;
  copy_link: boolean;
  qr: boolean;
  transfer: boolean;
  clients: boolean;
  usage_chart: boolean;
  info: boolean;
  delete_service: boolean;
}

export interface PanelSubscriptionSettings {
  default_group_ids: number[];
  user_limit: number | null;
  display_mode: string;
  node_prefixes: string[];
  show_prefixes_in_locations: boolean;
  link_mode: string;
  single_config_link_indexes: string;
  admin_login_path: string;
}

export interface PanelTrialSettings {
  enabled: boolean;
  volume_gb: number;
  duration_days: number;
}

export interface PanelRenewalSettings {
  auto_renew_enabled: boolean;
  webhook_notifications_enabled: boolean;
  renew_volume_remaining_mode: boolean;
}

export interface PanelSalesSettings {
  shop_enabled: boolean;
  reseller_enabled: boolean;
}

export interface PanelCustomBuySettings {
  enabled: boolean;
  price_per_gb: number;
  price_per_day: number;
  min_gb: number;
  max_gb: number;
  min_days: number;
  max_days: number;
  ip_limit: number;
}

export interface PanelResellerCapacitySettings {
  enabled: boolean;
  price_per_user: number;
}

export interface PanelResellerButtonSettings {
  credentials: boolean;
  change_password: boolean;
  toggle_status: boolean;
  usage_report: boolean;
  usage_cap: boolean;
  buy_user_capacity: boolean;
  delete: boolean;
}

export interface PanelDetailSettingsResponse extends PanelEnvelope {
  code: number;
  buttons: PanelButtonSettings;
  subscription: PanelSubscriptionSettings;
  trial: PanelTrialSettings;
  renewal: PanelRenewalSettings;
  sales: PanelSalesSettings;
  custom_buy: PanelCustomBuySettings;
  reseller_capacity: PanelResellerCapacitySettings;
  reseller_buttons: PanelResellerButtonSettings;
}

/** Every group is optional — only send the groups that changed. */
export interface PanelDetailSettingsSaveRequest extends PanelAuthRequest {
  code: number;
  buttons?: Partial<PanelButtonSettings>;
  subscription?: Partial<PanelSubscriptionSettings>;
  trial?: Partial<PanelTrialSettings>;
  renewal?: Partial<PanelRenewalSettings>;
  sales?: Partial<PanelSalesSettings>;
  custom_buy?: Partial<PanelCustomBuySettings>;
  reseller_capacity?: Partial<PanelResellerCapacitySettings>;
  reseller_buttons?: Partial<PanelResellerButtonSettings>;
}

export interface PanelStatusResponse extends PanelEnvelope {
  code: number;
  name: string;
  enable: boolean;
  shop_enabled: boolean;
  reseller_enabled: boolean;
  auth_type: string;
  base_url: string;
  tunnel_url?: string | null;

  status_error?: string | null;
  version?: string | null;
  mem_total?: number | null;
  mem_used?: number | null;
  cpu_cores?: number | null;
  cpu_usage?: number | null;
  total_user?: number | null;
  online_users?: number | null;
  active_users?: number | null;
  on_hold_users?: number | null;
  disabled_users?: number | null;
  expired_users?: number | null;
  limited_users?: number | null;
  incoming_bandwidth?: number | null;
  outgoing_bandwidth?: number | null;
}

export interface PanelGroupOption {
  id: number;
  name: string;
}

export interface PanelGroupsResponse extends PanelEnvelope {
  groups: PanelGroupOption[];
}

export interface PanelButtonStyleResponse extends PanelEnvelope {
  text: string;
  style: string;
  icon_id?: string | null;
}

export interface PanelButtonStyleSaveRequest extends PanelAuthRequest {
  code: number;
  text?: string;
  style?: string;
  icon_id?: string;
  clear_icon?: boolean;
}
