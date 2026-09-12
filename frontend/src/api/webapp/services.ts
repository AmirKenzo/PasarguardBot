import type {
  WebAppChangeLinkRequest,
  WebAppChangeResponse,
  WebAppChangeSubscriptionRequest,
  WebAppClientsRequest,
  WebAppClientsResponse,
  WebAppConfigLinksRequest,
  WebAppConfigLinksResponse,
  WebAppServiceDetailRequest,
  WebAppServiceDetailResponse,
  WebAppServicesRequest,
  WebAppServicesResponse,
} from "../../types/webapp";
import { apiPost } from "./client";

export function getServices(body: WebAppServicesRequest) {
  return apiPost<WebAppServicesResponse>("/services", body);
}

export function getServiceDetail(body: WebAppServiceDetailRequest) {
  return apiPost<WebAppServiceDetailResponse>("/services/detail", body);
}

export function getConfigLinks(body: WebAppConfigLinksRequest) {
  return apiPost<WebAppConfigLinksResponse>("/services/config-links", body);
}

export function getServiceClients(body: WebAppClientsRequest) {
  return apiPost<WebAppClientsResponse>("/services/clients", body);
}

export function changeLink(body: WebAppChangeLinkRequest) {
  return apiPost<WebAppChangeResponse>("/change_link", body);
}

export function changeSubscription(body: WebAppChangeSubscriptionRequest) {
  return apiPost<WebAppChangeResponse>("/change_sub", body);
}
