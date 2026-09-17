import type {
  BalanceDepositCryptoRequest,
  BalanceDepositCryptoResponse,
  BalanceDepositManualReceiptResponse,
  BalanceDepositManualRequest,
  BalanceDepositManualResponse,
  BalanceMethodsResponse,
  BalancePhoneRequestResponse,
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
