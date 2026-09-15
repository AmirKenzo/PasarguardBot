/** Mirrors app/models/webapp/common.py */

export interface WebAppUserData {
  id: number;
  username?: string | null;
  first_name?: string | null;
  photo_url?: string | null;
}

export interface WebAppAuthRequest {
  session_token?: string | null;
  init_data?: string | null;
}

/** Raw fields only (bytes, unix timestamps, plain numbers) -- this is a webapp-only
 * model (the Telegram bot has its own separate formatting), so the frontend formats
 * everything itself for bilingual (fa/en) display. See src/lib/format.ts. */
export interface ServiceStatus {
  code: string;
  username: string;
  panel_name: string | null;
  status: string | null;
  used_traffic_bytes: number;
  remaining_traffic_bytes: number;
  total_traffic_bytes: number;
  expiration_timestamp?: number | null;
  subscription_url: string | null;
  ip_limit?: number | null;
  helper_subscription_url?: string | null;
  config_value?: number | null;
  lifetime_used_traffic?: number | null;
  last_connection?: number | null;
  last_edit?: number | null;
  reset_strategy?: string | null;
  total_possible_traffic?: number | null;
  single_config_links: string[];
  is_test?: boolean;
}

export interface ServiceButtons {
  copy_link: boolean;
  change_link: boolean;
  change_sub: boolean;
  tamdid: boolean;
  extend_time: boolean;
  extra_volume: boolean;
  qr: boolean;
  other_links: boolean;
  transfer_config: boolean;
  client_list: boolean;
  usage_chart: boolean;
}

export interface TransactionStats {
  count: number;
  total_amount: number;
}

export interface TransactionStatsSummary {
  manual: TransactionStats;
  crypto: TransactionStats;
}

export interface DiscountInfo {
  code: string;
  percent: number;
  times_used: number;
  usage_limit: number;
  is_public: boolean;
  expiration_timestamp?: number | null;
}

export interface UserProfile {
  id: number;
  username: string | null;
  first_name: string | null;
  photo_url: string | null;
  invite: number;
  amount: number;
  safe: boolean;
  number: string | null;
  join_date?: number | null;
  discount: DiscountInfo | null;
  transactions: TransactionStatsSummary;
}
