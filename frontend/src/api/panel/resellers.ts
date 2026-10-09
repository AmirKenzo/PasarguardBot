import type {
  ActionResponse,
  PanelAuthRequest,
  PanelResellerCodeRequest,
  PanelResellerDeleteRequest,
  PanelResellerDetailRequest,
  PanelResellerDetailResponse,
  PanelResellerEventsRequest,
  PanelResellerEventsResponse,
  PanelResellerExtendRequest,
  PanelResellerLedgerRequest,
  PanelResellerLedgerResponse,
  PanelResellerMaxUsersRequest,
  PanelResellerOverviewResponse,
  PanelResellerPasswordResponse,
  PanelResellerPlanDeleteRequest,
  PanelResellerPlansResponse,
  PanelResellerPlanSaveRequest,
  PanelResellerRenewRequest,
  PanelResellerRolesRequest,
  PanelResellerRolesResponse,
  PanelResellersRequest,
  PanelResellersResponse,
  PanelResellerSettingsResponse,
  PanelResellerSettingsSaveRequest,
  PanelResellerUsageCapRequest,
} from "../../types/panel";
import { panelPost } from "./client";

export function getOverview(body: PanelAuthRequest) {
  return panelPost<PanelResellerOverviewResponse>("/resellers/overview", body);
}

export function listResellers(body: PanelResellersRequest) {
  return panelPost<PanelResellersResponse>("/resellers", body);
}

export function getReseller(body: PanelResellerDetailRequest) {
  return panelPost<PanelResellerDetailResponse>("/resellers/detail", body);
}

export function pauseReseller(body: PanelResellerCodeRequest) {
  return panelPost<ActionResponse>("/resellers/pause", body);
}

export function resumeReseller(body: PanelResellerCodeRequest) {
  return panelPost<ActionResponse>("/resellers/resume", body);
}

export function revealPassword(body: PanelResellerCodeRequest) {
  return panelPost<PanelResellerPasswordResponse>("/resellers/password", body);
}

export function resetPassword(body: PanelResellerCodeRequest) {
  return panelPost<PanelResellerPasswordResponse>("/resellers/password/reset", body);
}

export function renewReseller(body: PanelResellerRenewRequest) {
  return panelPost<ActionResponse>("/resellers/renew", body);
}

export function extendReseller(body: PanelResellerExtendRequest) {
  return panelPost<ActionResponse>("/resellers/extend", body);
}

export function setUsageCap(body: PanelResellerUsageCapRequest) {
  return panelPost<ActionResponse>("/resellers/usage-cap", body);
}

export function setMaxUsers(body: PanelResellerMaxUsersRequest) {
  return panelPost<ActionResponse>("/resellers/max-users", body);
}

export function deleteReseller(body: PanelResellerDeleteRequest) {
  return panelPost<ActionResponse>("/resellers/delete", body);
}

export function getLedger(body: PanelResellerLedgerRequest) {
  return panelPost<PanelResellerLedgerResponse>("/resellers/ledger", body);
}

export function listEvents(body: PanelResellerEventsRequest) {
  return panelPost<PanelResellerEventsResponse>("/resellers/events", body);
}

export function getSettings(body: PanelAuthRequest) {
  return panelPost<PanelResellerSettingsResponse>("/resellers/settings", body);
}

export function saveSettings(body: PanelResellerSettingsSaveRequest) {
  return panelPost<ActionResponse>("/resellers/settings/save", body);
}

export function listResellerPlans(body: PanelAuthRequest) {
  return panelPost<PanelResellerPlansResponse>("/reseller-plans", body);
}

export function saveResellerPlan(body: PanelResellerPlanSaveRequest) {
  return panelPost<ActionResponse>("/reseller-plans/save", body);
}

export function listPanelRoles(body: PanelResellerRolesRequest) {
  return panelPost<PanelResellerRolesResponse>("/reseller-plans/roles", body);
}

export function deleteResellerPlan(body: PanelResellerPlanDeleteRequest) {
  return panelPost<ActionResponse>("/reseller-plans/delete", body);
}
