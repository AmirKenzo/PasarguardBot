/** Mirrors app/models/webapp/balance.py */
import type { WebAppAuthRequest } from "./common";

export type WebAppBalanceMethodsRequest = WebAppAuthRequest;

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
  zarinpal_enabled: boolean;
  zarinpal_sandbox: boolean;
  zarinpal_deposit_min: number;
  zarinpal_deposit_max: number;
  zarinpal_bonus_percent: number;
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
}

export interface BalanceDepositManualReceiptResponse {
  ok: boolean;
  message?: string | null;
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

export interface ZarinpalPayment {
  id: number;
  order_id: string;
  amount: number;
  status: string;
  status_label: string;
  sandbox: boolean;
  payment_url?: string | null;
  ref_id?: string | null;
}

export interface BalanceZarinpalPaymentResponse {
  ok: boolean;
  message?: string | null;
  payment?: ZarinpalPayment | null;
  error?: string | null;
}
