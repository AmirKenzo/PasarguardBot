/** Mirrors app/models/panel/services.py */
import type { PagedRequest, PageMeta, PanelAuthRequest, PanelEnvelope, PanelOption } from "./common";

export interface PanelServiceRow {
  code: number;
  user_id?: number | null;
  username?: string | null;
  panel?: string | null;
  panel_code?: number | null;
  package_size?: number | null;
  expiration_time?: number | null;
  enable: boolean;
  expired: boolean;
  is_test: boolean;
}

export interface PanelServicesRequest extends PagedRequest {
  q?: string;
  /** Panel code, or empty for all. */
  panel?: string;
  /** empty | active | expired | test */
  state?: string;
}

export interface PanelServicesResponse extends PanelEnvelope {
  services: PanelServiceRow[];
  panels: PanelOption[];
  meta: PageMeta;
}

export interface PanelServiceToggleRequest extends PanelAuthRequest {
  code: number;
  enabled: boolean;
}

export interface PanelServiceDeleteRequest extends PanelAuthRequest {
  code: number;
}

export interface PanelTransactionRow {
  id: number;
  user_id?: number | null;
  amount: number;
  status?: string | null;
  method?: string | null;
  created_at?: number | null;
  receipt?: string | null;
}

export interface PanelTransactionsRequest extends PagedRequest {
  /** empty | pending | approved | rejected */
  status?: string;
  /** empty | card | crypto */
  method?: string;
}

export interface PanelTransactionsResponse extends PanelEnvelope {
  transactions: PanelTransactionRow[];
  meta: PageMeta;
  pending_total: number;
}

export interface PanelTransactionActionRequest extends PanelAuthRequest {
  tx_id: number;
}
