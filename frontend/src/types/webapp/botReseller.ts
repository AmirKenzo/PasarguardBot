/** Mirrors app/models/webapp/bot_reseller.py */

import type { WebAppAuthRequest } from "./common";

export interface BotResellerOk {
  ok: boolean;
  error?: string | null;
}

export interface BotResellerServiceItem {
  id: number;
  name: string;
  price_per_gb: number;
  max_users: number;
  max_user_gb: number;
  max_user_days: number;
  users: number;
  usage_24h_bytes: number;
}

export interface BotResellerStateResponse extends BotResellerOk {
  is_reseller: boolean;
  status: "active" | "frozen" | "suspended" | null;
  balance: number;
  burn_per_hour: number;
  runway_hours: number | null;
  usage_24h_bytes: number;
  usage_24h_amount: number;
  services: BotResellerServiceItem[];
  pending: string[];
  username_prefix: string;
  username_suffix: string;
}

export interface BotResellerUserItem {
  id: number;
  name: string;
  username: string;
  service_id: number;
  service_name: string;
  note: string | null;
  status: string | null;
  disabled_by: "system" | "reseller" | "admin" | null;
  used_bytes: number;
  limit_bytes: number;
  expire: number | null;
  online_at: number | null;
  cost: number;
  live: boolean;
}

export interface BotResellerUsersRequest extends WebAppAuthRequest {
  service_id?: number | null;
}

export interface BotResellerUsersResponse extends BotResellerOk {
  users: BotResellerUserItem[];
  live_error: boolean;
}

export interface BotResellerUserRequest extends WebAppAuthRequest {
  id: number;
}

export interface BotResellerUserResponse extends BotResellerOk {
  user: BotResellerUserItem | null;
  subscription_url: string | null;
}

export interface BotResellerCreateRequest extends WebAppAuthRequest {
  service_id: number;
  name: string;
  gb: number;
  days: number;
  note?: string | null;
}

export interface BotResellerEditRequest extends WebAppAuthRequest {
  id: number;
  gb: number;
  days: number;
  note?: string | null;
}

export interface BotResellerToggleRequest extends WebAppAuthRequest {
  id: number;
  enabled: boolean;
}

export interface BotResellerUsageRow {
  hour: number;
  service_id: number;
  service_name: string;
  bytes: number;
  amount: number;
}

export interface BotResellerUsageResponse extends BotResellerOk {
  rows: BotResellerUsageRow[];
}
