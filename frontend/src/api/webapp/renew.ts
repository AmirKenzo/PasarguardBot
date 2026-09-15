import type {
  WebAppRenewConfirmRequest,
  WebAppRenewConfirmResponse,
  WebAppRenewOptionsRequest,
  WebAppRenewOptionsResponse,
} from "../../types/webapp";
import { apiPost } from "./client";

export function getRenewOptions(body: WebAppRenewOptionsRequest) {
  return apiPost<WebAppRenewOptionsResponse>("/renew/options", body);
}

export function confirmRenew(body: WebAppRenewConfirmRequest) {
  return apiPost<WebAppRenewConfirmResponse>("/renew/confirm", body);
}
