/** Mirrors app/models/panel/payments.py */
import type { PanelAuthRequest, PanelEnvelope } from "./common";

export const WALLET_TYPES = ["TRX", "USDT", "TON"] as const;

export interface PanelWalletRow {
  id: number;
  type: string;
  address: string;
  has_api_key: boolean;
}

export interface PanelCardRow {
  id: number;
  number: string;
  name: string;
  active: boolean;
}

export interface PanelAutoApproveRuleRow {
  id: number;
  min_successful_tx: number;
  max_successful_tx?: number | null;
  auto_approve_delay_minutes: number;
  is_active: boolean;
}

export interface PanelPaymentsResponse extends PanelEnvelope {
  wallets: PanelWalletRow[];
  available_wallet_types: string[];
  cards: PanelCardRow[];
  rules: PanelAutoApproveRuleRow[];
}

export interface PanelWalletCreateRequest extends PanelAuthRequest {
  wallet_type: string;
  address: string;
  api_key?: string;
}

export interface PanelWalletDeleteRequest extends PanelAuthRequest {
  wallet_id: number;
}

export interface PanelCardCreateRequest extends PanelAuthRequest {
  number: string;
  name: string;
  active?: boolean;
}

export interface PanelCardActionRequest extends PanelAuthRequest {
  card_id: number;
}

export interface PanelRuleCreateRequest extends PanelAuthRequest {
  min_successful_tx?: number;
  max_successful_tx?: number | null;
  auto_approve_delay_minutes?: number;
}

export interface PanelRuleToggleRequest extends PanelAuthRequest {
  rule_id: number;
  is_active: boolean;
}

export interface PanelRuleDeleteRequest extends PanelAuthRequest {
  rule_id: number;
}

export type PanelTonPaysMode = "standard" | "custom";

export interface PanelTonPaysStats {
  paid_today: number;
  amount_today: number;
  open_invoices: number;
  failed_today: number;
}

export interface PanelTonPaysResponse extends PanelEnvelope {
  enabled: boolean;
  mode: PanelTonPaysMode;
  api_key_masked: string;
  custom_key_masked: string;
  has_api_key: boolean;
  has_custom_key: boolean;
  ready: boolean;
  deposit_min: number;
  deposit_max: number;
  bonus_enabled: boolean;
  bonus_percent: number;
  webhook_url?: string | null;
  stats: PanelTonPaysStats;
}

export interface PanelTonPaysSaveRequest extends PanelAuthRequest {
  enabled?: boolean;
  mode?: PanelTonPaysMode;
  api_key?: string;
  custom_key?: string;
  clear_api_key?: boolean;
  clear_custom_key?: boolean;
  deposit_min?: number;
  deposit_max?: number;
  bonus_enabled?: boolean;
  bonus_percent?: number;
}

export interface PanelTonPaysTestRequest extends PanelAuthRequest {
  mode: PanelTonPaysMode;
  api_key?: string;
}
