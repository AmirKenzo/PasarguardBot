import type {
  ActionResponse,
  PanelUserBalanceRequest,
  PanelUserBalanceResponse,
  PanelUserBlockRequest,
  PanelUserDetailRequest,
  PanelUserDetailResponse,
  PanelUserMessageRequest,
  PanelUsersRequest,
  PanelUsersResponse,
} from "../../types/panel";
import { panelPost } from "./client";

export function listUsers(body: PanelUsersRequest) {
  return panelPost<PanelUsersResponse>("/users", body);
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

export function sendMessage(body: PanelUserMessageRequest) {
  return panelPost<ActionResponse>("/users/message", body);
}
