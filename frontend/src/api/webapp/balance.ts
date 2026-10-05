import type {
  BalanceDepositCryptoRequest,
  BalanceDepositCryptoResponse,
  BalanceDepositManualReceiptResponse,
  BalanceDepositManualRequest,
  BalanceDepositManualResponse,
  BalanceDepositStarsRequest,
  BalanceDepositStarsResponse,
  BalanceMethodsResponse,
  BalancePhoneRequestResponse,
  BalanceTonPaysInvoiceResponse,
  WebAppBalanceMethodsRequest,
} from "../../types/webapp";
import type { AuthPayload } from "./client";
import { apiPost, apiPostForm } from "./client";

export function getBalanceMethods(body: WebAppBalanceMethodsRequest) {
  return apiPost<BalanceMethodsResponse>("/balance/methods", body);
}

export function requestPhoneVerification(auth: AuthPayload) {
  return apiPost<BalancePhoneRequestResponse>("/balance/phone/request", {}, auth);
}

export function depositManual(body: BalanceDepositManualRequest) {
  return apiPost<BalanceDepositManualResponse>("/balance/deposit/manual", body);
}

export function depositCrypto(body: BalanceDepositCryptoRequest) {
  return apiPost<BalanceDepositCryptoResponse>("/balance/deposit/crypto", body);
}

export function depositManualReceipt(auth: AuthPayload, amount: number, file: File) {
  const form = new FormData();
  form.set("amount", String(amount));
  form.set("file", file);
  return apiPostForm<BalanceDepositManualReceiptResponse>("/balance/deposit/manual/receipt", form, auth);
}

export function depositStars(body: BalanceDepositStarsRequest) {
  return apiPost<BalanceDepositStarsResponse>("/balance/deposit/stars", body);
}

export function depositTonPays(auth: AuthPayload, amount: number) {
  return apiPost<BalanceTonPaysInvoiceResponse>("/balance/deposit/tonpays", { amount }, auth);
}

export function getOpenTonPaysInvoice(auth: AuthPayload) {
  return apiPost<BalanceTonPaysInvoiceResponse>("/balance/tonpays/open", {}, auth);
}

export function checkTonPaysInvoice(auth: AuthPayload, invoice: number) {
  return apiPost<BalanceTonPaysInvoiceResponse>("/balance/tonpays/status", { invoice }, auth);
}

export function changeTonPaysCard(auth: AuthPayload, invoice: number) {
  return apiPost<BalanceTonPaysInvoiceResponse>("/balance/tonpays/change-card", { invoice }, auth);
}

export function sendTonPaysReceipt(auth: AuthPayload, invoice: number, file: File) {
  const form = new FormData();
  form.set("invoice", String(invoice));
  form.set("file", file);
  return apiPostForm<BalanceTonPaysInvoiceResponse>("/balance/tonpays/receipt", form, auth);
}
