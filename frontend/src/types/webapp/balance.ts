/** Mirrors app/models/webapp/balance.py */
import type { WebAppAuthRequest } from "./common";

export type WebAppBalanceMethodsRequest = WebAppAuthRequest;

export interface BalanceMethodsResponse {
  ok: boolean;
  pay_mode: boolean;
  arz_mode: boolean;
  manual_deposit_min: number;
  manual_deposit_max: number;
  crypto_deposit_min: number;
  crypto_deposit_max: number;
  card_number?: string | null;
  card_name?: string | null;
  manual_bonus_percent: number;
  crypto_bonus_percent: number;
  arz_usd: number;
  arz_trx: number;
  arz_ton: number;
  phone_verify_required: boolean;
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

export type CryptoCurrency = "trx" | "usdt" | "ton";

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
