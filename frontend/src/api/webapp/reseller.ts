import type {
  WebAppAuthRequest,
  WebAppResellerAccountResponse,
  WebAppResellerAccountsResponse,
  WebAppResellerActionResponse,
  WebAppResellerAddonPreviewResponse,
  WebAppResellerAddonRequest,
  WebAppResellerBuyConfirmResponse,
  WebAppResellerBuyOptionsResponse,
  WebAppResellerBuyPreviewResponse,
  WebAppResellerBuyRequest,
  WebAppResellerCapacityPreviewResponse,
  WebAppResellerCapacityRequest,
  WebAppResellerCodeRequest,
  WebAppResellerEventsResponse,
  WebAppResellerPageRequest,
  WebAppResellerPasswordResponse,
  WebAppResellerRenewPreviewResponse,
  WebAppResellerRenewRequest,
  WebAppResellerUsageCapRequest,
  WebAppResellerUsageResponse,
  WebAppResellerUsernameRequest,
  WebAppResellerUsernameResponse,
} from "../../types/webapp";
import { apiPost } from "./client";

export function getBuyOptions(body: WebAppAuthRequest) {
  return apiPost<WebAppResellerBuyOptionsResponse>("/reseller/buy/options", body);
}

export function suggestUsername(body: WebAppResellerUsernameRequest) {
  return apiPost<WebAppResellerUsernameResponse>("/reseller/buy/username", body);
}

export function previewBuy(body: WebAppResellerBuyRequest) {
  return apiPost<WebAppResellerBuyPreviewResponse>("/reseller/buy/preview", body);
}

export function confirmBuy(body: WebAppResellerBuyRequest) {
  return apiPost<WebAppResellerBuyConfirmResponse>("/reseller/buy/confirm", body);
}

export function listAccounts(body: WebAppAuthRequest) {
  return apiPost<WebAppResellerAccountsResponse>("/reseller/accounts", body);
}

export function getAccount(body: WebAppResellerCodeRequest) {
  return apiPost<WebAppResellerAccountResponse>("/reseller/account", body);
}

export function revealPassword(body: WebAppResellerCodeRequest) {
  return apiPost<WebAppResellerPasswordResponse>("/reseller/account/password", body);
}

export function resetPassword(body: WebAppResellerCodeRequest) {
  return apiPost<WebAppResellerPasswordResponse>("/reseller/account/password/reset", body);
}

export function pause(body: WebAppResellerCodeRequest) {
  return apiPost<WebAppResellerActionResponse>("/reseller/account/pause", body);
}

export function resume(body: WebAppResellerCodeRequest) {
  return apiPost<WebAppResellerActionResponse>("/reseller/account/resume", body);
}

export function previewRenew(body: WebAppResellerRenewRequest) {
  return apiPost<WebAppResellerRenewPreviewResponse>("/reseller/account/renew/preview", body);
}

export function confirmRenew(body: WebAppResellerRenewRequest) {
  return apiPost<WebAppResellerActionResponse>("/reseller/account/renew/confirm", body);
}

export function setUsageCap(body: WebAppResellerUsageCapRequest) {
  return apiPost<WebAppResellerActionResponse>("/reseller/account/usage-cap", body);
}

export function previewCapacity(body: WebAppResellerCapacityRequest) {
  return apiPost<WebAppResellerCapacityPreviewResponse>("/reseller/account/capacity/preview", body);
}

export function confirmCapacity(body: WebAppResellerCapacityRequest) {
  return apiPost<WebAppResellerActionResponse>("/reseller/account/capacity/confirm", body);
}

export function previewAddon(body: WebAppResellerAddonRequest) {
  return apiPost<WebAppResellerAddonPreviewResponse>("/reseller/account/addon/preview", body);
}

export function confirmAddon(body: WebAppResellerAddonRequest) {
  return apiPost<WebAppResellerActionResponse>("/reseller/account/addon/confirm", body);
}

export function getUsage(body: WebAppResellerPageRequest) {
  return apiPost<WebAppResellerUsageResponse>("/reseller/account/usage", body);
}

export function getEvents(body: WebAppResellerPageRequest) {
  return apiPost<WebAppResellerEventsResponse>("/reseller/account/events", body);
}

export function deleteAccount(body: WebAppResellerCodeRequest) {
  return apiPost<WebAppResellerActionResponse>("/reseller/account/delete", body);
}
