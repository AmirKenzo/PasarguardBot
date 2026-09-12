/** Mirrors app/models/webapp/services.py */
import type { WebAppAuthRequest, ServiceButtons, ServiceStatus } from "./common";

export interface WebAppChangeLinkRequest {
  code: number;
  init_data?: string | null;
  username?: string | null;
  password?: string | null;
  session_token?: string | null;
}

export interface WebAppChangeSubscriptionRequest {
  code: number;
  init_data?: string | null;
  username?: string | null;
  password?: string | null;
  session_token?: string | null;
}

export interface WebAppServicesRequest extends WebAppAuthRequest {
  page?: number;
  limit?: number;
  search?: string | null;
  panel_code?: number | null;
}

export interface PanelGroupItem {
  panel_code: number;
  panel_name: string;
  service_count: number;
}

export interface WebAppServicesResponse {
  ok: boolean;
  services?: ServiceStatus[] | null;
  total: number;
  page: number;
  limit: number;
  total_pages: number;
  grouping_enabled: boolean;
  panel_groups?: PanelGroupItem[] | null;
  error?: string | null;
}

export interface WebAppServiceDetailRequest extends WebAppAuthRequest {
  code: number;
}

export interface WebAppServiceDetailResponse {
  ok: boolean;
  service?: ServiceStatus | null;
  buttons?: ServiceButtons | null;
  error?: string | null;
}

export interface WebAppConfigLinkItem {
  index: number;
  name: string;
  url: string;
}

export interface WebAppConfigLinksRequest extends WebAppAuthRequest {
  code: number;
  page?: number;
  limit?: number;
}

export interface WebAppConfigLinksResponse {
  ok: boolean;
  links: WebAppConfigLinkItem[];
  total: number;
  page: number;
  total_pages: number;
  error?: string | null;
}

export interface WebAppClientItem {
  created_at: number;
  created_at_text: string;
  time_ago?: string | null;
  user_agent: string;
  app_name: string;
  version?: string | null;
  platform?: string | null;
  ip_address?: string | null;
  hwid?: string | null;
}

export interface WebAppClientsRequest extends WebAppAuthRequest {
  code: number;
}

export interface WebAppClientsResponse {
  ok: boolean;
  clients: WebAppClientItem[];
  error?: string | null;
}
