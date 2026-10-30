import type {
  ActionResponse,
  BotGrantApproveRequest,
  BotGrantIdRequest,
  BotGrantManualRequest,
  BotGrantRejectRequest,
  BotRequestsResponse,
  BotResellerDetailResponse,
  BotResellerIdRequest,
  BotResellerNamingRequest,
  BotResellersResponse,
  BotResellerUserIdRequest,
  BotServiceGroupsRequest,
  BotServiceGroupsResponse,
  BotServiceSaveRequest,
  BotServicesResponse,
  BotServiceToggleRequest,
  BotSettingsResponse,
  BotSettingsSaveRequest,
  PanelAuthRequest,
} from "../../types/panel";
import { panelPost } from "./client";

export function listServices(body: PanelAuthRequest) {
  return panelPost<BotServicesResponse>("/bot-resellers/services", body);
}

export function panelGroups(body: BotServiceGroupsRequest) {
  return panelPost<BotServiceGroupsResponse>("/bot-resellers/groups", body);
}

export function readSettings(body: PanelAuthRequest) {
  return panelPost<BotSettingsResponse>("/bot-resellers/settings", body);
}

export function saveSettings(body: BotSettingsSaveRequest) {
  return panelPost<ActionResponse>("/bot-resellers/settings/save", body);
}

export function toggleService(body: BotServiceToggleRequest) {
  return panelPost<ActionResponse>("/bot-resellers/services/toggle", body);
}

export function saveService(body: BotServiceSaveRequest) {
  return panelPost<ActionResponse>("/bot-resellers/services/save", body);
}

export function listRequests(body: PanelAuthRequest) {
  return panelPost<BotRequestsResponse>("/bot-resellers/requests", body);
}

export function approve(body: BotGrantApproveRequest) {
  return panelPost<ActionResponse>("/bot-resellers/requests/approve", body);
}

export function reject(body: BotGrantRejectRequest) {
  return panelPost<ActionResponse>("/bot-resellers/requests/reject", body);
}

export function grantManually(body: BotGrantManualRequest) {
  return panelPost<ActionResponse>("/bot-resellers/grant", body);
}

export function updateTerms(body: BotGrantApproveRequest) {
  return panelPost<ActionResponse>("/bot-resellers/grant/terms", body);
}

export function revoke(body: BotGrantIdRequest) {
  return panelPost<ActionResponse>("/bot-resellers/grant/revoke", body);
}

export function listResellers(body: PanelAuthRequest) {
  return panelPost<BotResellersResponse>("/bot-resellers", body);
}

export function detail(body: BotResellerIdRequest) {
  return panelPost<BotResellerDetailResponse>("/bot-resellers/detail", body);
}

export function suspend(body: BotResellerIdRequest) {
  return panelPost<ActionResponse>("/bot-resellers/suspend", body);
}

export function unsuspend(body: BotResellerIdRequest) {
  return panelPost<ActionResponse>("/bot-resellers/unsuspend", body);
}

export function setNaming(body: BotResellerNamingRequest) {
  return panelPost<ActionResponse>("/bot-resellers/naming", body);
}

export function deleteUser(body: BotResellerUserIdRequest) {
  return panelPost<ActionResponse>("/bot-resellers/users/delete", body);
}
