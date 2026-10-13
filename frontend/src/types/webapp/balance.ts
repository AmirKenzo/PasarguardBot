/** Mirrors app/models/webapp/balance.py */
import type { WebAppAuthRequest } from "./common";

export type WebAppBalanceMethodsRequest = WebAppAuthRequest;

/** An Iranian direct gateway this user may pay with (mirrors IrGatewayMethod). */
export interface IrGatewayMethod {
  key: string;
  title: string;
  sandbox: boolean;
  deposit_min: number;
  deposit_max: number;
  bonus_percent: number;
}

export interface BalanceMethodsResponse {
  ok: boolean;
  pay_mode: boolean;
  arz_mode: boolean;
  cart_sta: boolean;
  manual_deposit_min: number;
  manual_deposit_max: number;
  crypto_deposit_min: number;
  crypto_deposit_max: number;
  card_number?: string | null;
  card_name?: string | null;
  manual_bonus_percent: number;
  crypto_bonus_percent: number;
  stars_bonus_percent: number;
  arz_usd: number;
  arz_trx: number;
  arz_ton: number;
  arz_pol: number;
  phone_verify_required: boolean;
  tonpays_enabled: boolean;
  tonpays_mode: TonPaysMode;
  tonpays_deposit_min: number;
  tonpays_deposit_max: number;
  tonpays_bonus_percent: number;
  ir_gateways: IrGatewayMethod[];
  error?: string | null;
}

export interface BalancePhoneRequestResponse {
  ok: boolean;
  error?: string | null;
}

export interface BalanceDepositManualRequest extends WebAppAuthRequest {
  amount: number;
}

export interface BalanceDepositManualResponse {
  ok: boolean;
  message?: string | null;
  card_number?: string | null;
  card_name?: string | null;
  error?: string | null;
  forapp_enabled?: boolean;
  tx_id?: number | null;
  base_amount?: number | null;
  payable_amount?: number | null;
  payable_rial?: number | null;
  amount_offset?: number | null;
  forapp_ttl_minutes?: number | null;
}

export interface BalanceDepositManualReceiptResponse {
  ok: boolean;
  message?: string | null;
  error?: string | null;
  already_approved?: boolean;
}

export interface BalanceDepositManualStatusResponse {
  ok: boolean;
  status?: string | null;
  payable_amount?: number | null;
  error?: string | null;
}

export type CryptoCurrency = "trx" | "usdt" | "usdt-ton" | "usdt-bep20" | "ton" | "pol";

export interface BalanceDepositCryptoRequest extends WebAppAuthRequest {
  amount: number;
  currency: CryptoCurrency;
}

export interface BalanceDepositCryptoResponse {
  ok: boolean;
  order_id?: number | null;
  wallet_address?: string | null;
  amount_crypto?: string | null;
  amount_irt?: number | null;
  currency?: string | null;
  error?: string | null;
}

export interface BalanceDepositStarsRequest extends WebAppAuthRequest {
  amount: number;
}

export interface BalanceDepositStarsResponse {
  ok: boolean;
  message?: string | null;
  tx_id?: number | null;
  invoice_no?: string | null;
  amount_irt?: number | null;
  stars?: number | null;
  usd_rate_irt?: number | null;
  star_price_irt?: number | null;
  invoice_url?: string | null;
  error?: string | null;
}

export type TonPaysMode = "standard" | "custom";

export interface TonPaysInvoice {
  id: number;
  invoice_id?: string | null;
  mode: TonPaysMode;
  amount: number;
  final_amount?: number | null;
  status: string;
  status_label: string;
  invoice_url?: string | null;
  web_invoice_url?: string | null;
  card_number?: string | null;
  card_name?: string | null;
  receipt_sent: boolean;
}

export interface BalanceTonPaysInvoiceResponse {
  ok: boolean;
  message?: string | null;
  invoice?: TonPaysInvoice | null;
  error?: string | null;
}

export interface IrGatewayPayment {
  id: number;
  gateway: string;
  gateway_title: string;
  order_id: string;
  amount: number;
  status: string;
  status_label: string;
  sandbox: boolean;
  payment_url?: string | null;
  ref_id?: string | null;
}

export interface BalanceIrGatewayPaymentResponse {
  ok: boolean;
  message?: string | null;
  payment?: IrGatewayPayment | null;
  error?: string | null;
}
