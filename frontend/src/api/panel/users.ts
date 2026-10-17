import type {
  ActionResponse,
  PanelAuthRequest,
  PanelUserBalanceRequest,
  PanelUserBalanceResponse,
  PanelUserBlockRequest,
  PanelUserDetailRequest,
  PanelUserDetailResponse,
  PanelTransferAdminsRequest,
  PanelTransferAdminsResponse,
  PanelTransferPreviewRequest,
  PanelTransferPreviewResponse,
  PanelTransferStartRequest,
  PanelTransferStartResponse,
  PanelTransferStatusRequest,
  PanelTransferStatusResponse,
  PanelUserMessageRequest,
  PanelUserPhoneRequest,
  PanelUserPhoneResponse,
  PanelUsersRequest,
  PanelUsersResponse,
  PanelUsersStatsResponse,
} from "../../types/panel";
import { panelPost } from "./client";

export function listUsers(body: PanelUsersRequest) {
  return panelPost<PanelUsersResponse>("/users", body);
}

export function usersStats(body: PanelAuthRequest) {
  return panelPost<PanelUsersStatsResponse>("/users/stats", body);
}

export function getUser(body: PanelUserDetailRequest) {
  return panelPost<PanelUserDetailResponse>("/users/detail", body);
}

export function adjustBalance(body: PanelUserBalanceRequest) {
  return panelPost<PanelUserBalanceResponse>("/users/balance", body);
}

export function setBlocked(body: PanelUserBlockRequest) {
  return panelPost<ActionResponse>("/users/block", body);
}

export function setPhone(body: PanelUserPhoneRequest) {
  return panelPost<PanelUserPhoneResponse>("/users/phone", body);
}

export function sendMessage(body: PanelUserMessageRequest) {
  return panelPost<ActionResponse>("/users/message", body);
}

export function transferAdmins(body: PanelTransferAdminsRequest) {
  return panelPost<PanelTransferAdminsResponse>("/users/transfer/admins", body);
}

export function transferPreview(body: PanelTransferPreviewRequest) {
  return panelPost<PanelTransferPreviewResponse>("/users/transfer/preview", body);
}

export function transferStart(body: PanelTransferStartRequest) {
  return panelPost<PanelTransferStartResponse>("/users/transfer/start", body);
}

export function transferStatus(body: PanelTransferStatusRequest) {
  return panelPost<PanelTransferStatusResponse>("/users/transfer/status", body);
}
