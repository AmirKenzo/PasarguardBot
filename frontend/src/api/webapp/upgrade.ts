import type {
  WebAppExtendTimeConfirmRequest,
  WebAppExtendTimeConfirmResponse,
  WebAppExtendTimeOptionsRequest,
  WebAppExtendTimeOptionsResponse,
  WebAppExtraVolumeConfirmRequest,
  WebAppExtraVolumeConfirmResponse,
  WebAppExtraVolumeOptionsRequest,
  WebAppExtraVolumeOptionsResponse,
  WebAppTransferConfigRequest,
  WebAppTransferConfigResponse,
} from "../../types/webapp";
import { apiPost } from "./client";

export function getExtendTimeOptions(body: WebAppExtendTimeOptionsRequest) {
  return apiPost<WebAppExtendTimeOptionsResponse>("/services/extend-time/options", body);
}

export function confirmExtendTime(body: WebAppExtendTimeConfirmRequest) {
  return apiPost<WebAppExtendTimeConfirmResponse>("/services/extend-time/confirm", body);
}

export function getExtraVolumeOptions(body: WebAppExtraVolumeOptionsRequest) {
  return apiPost<WebAppExtraVolumeOptionsResponse>("/services/extra-volume/options", body);
}

export function confirmExtraVolume(body: WebAppExtraVolumeConfirmRequest) {
  return apiPost<WebAppExtraVolumeConfirmResponse>("/services/extra-volume/confirm", body);
}

export function transferConfig(body: WebAppTransferConfigRequest) {
  return apiPost<WebAppTransferConfigResponse>("/services/transfer", body);
}
