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

/** ``id`` is the raw per-source primary key as a string — unique within
 * ``source`` but not across sources, so the frontend keys rows on
 * `${source}-${id}`. Only source "tx" + method "manual_card" rows are ever
 * actionable; everything else confirms itself with no admin step. */
export interface PanelTransactionRow {
  id: string;
  source: string;
  method: string;
  user_id?: number | null;
  amount: number;
  status: string;
  created_at?: number | null;
  has_receipt: boolean;
}

export interface PanelTransactionStats {
  pending: number;
  approved_7d: number;
  rejected_7d: number;
  approved_volume_7d: number;
}

export interface PanelTransactionsRequest extends PagedRequest {
  tx_id?: string;
  user_id?: string;
  amount?: string;
  /** empty | manual_card | crypto */
  method?: string;
  /** empty | pending | approved | rejected | needs_fix | expired */
  status?: string;
  /** 0 = all time, else last N days */
  days?: number;
}

export interface PanelTransactionsResponse extends PanelEnvelope {
  transactions: PanelTransactionRow[];
  meta: PageMeta;
  pending_total: number;
  stats: PanelTransactionStats;
}

export interface PanelTransactionActionRequest extends PanelAuthRequest {
  tx_id: number;
}

export interface PanelReceiptLinkRequest extends PanelAuthRequest {
  tx_id: number;
}

export interface PanelReceiptLinkResponse extends PanelEnvelope {
  url?: string | null;
}
