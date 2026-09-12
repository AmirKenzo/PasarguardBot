import type {
  WebAppBuyConfirmRequest,
  WebAppBuyConfirmResponse,
  WebAppBuyOptionsRequest,
  WebAppBuyOptionsResponse,
  WebAppBuyPlansRequest,
  WebAppBuyPlansResponse,
  WebAppBuyPreviewRequest,
  WebAppBuyPreviewResponse,
  WebAppBuyUsernameRequest,
  WebAppBuyUsernameResponse,
} from "../../types/webapp";
import { apiPost } from "./client";

export function getBuyOptions(body: WebAppBuyOptionsRequest) {
  return apiPost<WebAppBuyOptionsResponse>("/buy/options", body);
}

export function getBuyPlans(body: WebAppBuyPlansRequest) {
  return apiPost<WebAppBuyPlansResponse>("/buy/plans", body);
}

export function generateBuyUsername(body: WebAppBuyUsernameRequest) {
  return apiPost<WebAppBuyUsernameResponse>("/buy/username", body);
}

export function previewBuy(body: WebAppBuyPreviewRequest) {
  return apiPost<WebAppBuyPreviewResponse>("/buy/preview", body);
}

export function confirmBuy(body: WebAppBuyConfirmRequest) {
  return apiPost<WebAppBuyConfirmResponse>("/buy/confirm", body);
}
