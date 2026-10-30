/** Mirrors app/models/panel/bot_resellers.py */

import type { PanelAuthRequest } from "./common";

interface PanelOk {
  ok: boolean;
  error?: string | null;
}

export interface BotServiceRow {
  id: number;
  panel_code: number;
  panel_name: string | null;
  name: string;
  description: string | null;
  group_ids: number[];
  price_per_gb: number;
  sale_enabled: boolean;
  max_users: number;
  max_user_gb: number;
  max_user_days: number;
  resellers: number;
}

export interface BotServicesResponse extends PanelOk {
  services: BotServiceRow[];
  panels: { code: number; name: string }[];
}

export interface BotServiceGroupsRequest extends PanelAuthRequest {
  panel_code: number;
}

export interface BotServiceGroupsResponse extends PanelOk {
  groups: { id: number; name: string }[];
}

export interface BotServiceSaveRequest extends PanelAuthRequest {
  id?: number | null;
  panel_code: number;
  name: string;
  description?: string | null;
  group_ids: number[];
  price_per_gb: number;
  sale_enabled: boolean;
  max_users: number;
  max_user_gb: number;
  max_user_days: number;
}

export interface BotServiceToggleRequest extends PanelAuthRequest {
  id: number;
  sale_enabled: boolean;
}

export interface BotSettings {
  sale_mode: boolean;
}

export interface BotSettingsResponse extends PanelOk {
  settings: BotSettings;
  global_sale_mode: boolean;
  services_on_sale: number;
}

export interface BotSettingsSaveRequest extends PanelAuthRequest {
  settings: BotSettings;
}

export interface BotGrantTerms {
  price_per_gb?: number | null;
  max_users?: number | null;
  max_user_gb?: number | null;
  max_user_days?: number | null;
}

export interface BotGrantRow {
  id: number;
  reseller_id: number;
  telegram_id: number;
  service_id: number;
  service_name: string;
  status: "pending" | "approved" | "rejected" | "revoked";
  price_per_gb: number;
  max_users: number;
  max_user_gb: number;
  max_user_days: number;
  own_terms: BotGrantTerms;
  users: number;
  balance: number;
  reject_reason: string | null;
  requested_at: number;
  decided_at: number | null;
}

export interface BotRequestsResponse extends PanelOk {
  requests: BotGrantRow[];
}

export interface BotGrantIdRequest extends PanelAuthRequest {
  grant_id: number;
}

export interface BotGrantApproveRequest extends BotGrantIdRequest {
  terms: BotGrantTerms;
}

export interface BotGrantRejectRequest extends BotGrantIdRequest {
  reason?: string | null;
}

export interface BotGrantManualRequest extends PanelAuthRequest {
  telegram_id: number;
  service_id: number;
  terms: BotGrantTerms;
}

export interface BotResellerRow {
  id: number;
  telegram_id: number;
  status: "active" | "frozen" | "suspended";
  balance: number;
  users: number;
  usage_24h_bytes: number;
  usage_24h_amount: number;
  services: string[];
  username_prefix: string;
  username_suffix: string;
  created_at: number;
}

export interface BotResellersResponse extends PanelOk {
  resellers: BotResellerRow[];
}

export interface BotResellerIdRequest extends PanelAuthRequest {
  id: number;
}

export interface BotResellerNamingRequest extends BotResellerIdRequest {
  username_prefix: string;
  username_suffix: string;
}

export interface BotResellerUserRow {
  id: number;
  name: string;
  username: string;
  service_name: string;
  disabled_by: string | null;
  billed_bytes: number;
  cost: number;
  note: string | null;
  created_at: number;
}

export interface BotResellerDetailResponse extends PanelOk {
  reseller: BotResellerRow | null;
  grants: BotGrantRow[];
  users: BotResellerUserRow[];
}

export interface BotResellerUserIdRequest extends PanelAuthRequest {
  user_id: number;
}
