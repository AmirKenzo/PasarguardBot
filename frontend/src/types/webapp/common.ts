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

export interface ServiceStatus {
  code: string;
  username: string;
  panel_name: string | null;
  status: string | null;
  status_text: string;
  used_traffic: string;
  remaining_traffic: string;
  total_traffic: string;
  used_traffic_bytes: number;
  remaining_traffic_bytes: number;
  total_traffic_bytes: number;
  expiration_time: string;
  subscription_url: string;
  ip_limit_text?: string | null;
  helper_subscription_url?: string | null;
  config_value?: string | null;
  lifetime_used_traffic?: string | null;
  last_connection?: string | null;
  last_edit?: string | null;
  reset_strategy_text?: string | null;
  total_possible_traffic?: string | null;
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
  usage: string;
  type: string;
  expiration: string;
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
  join_date: string | null;
  discount: DiscountInfo | null;
  transactions: TransactionStatsSummary;
}
