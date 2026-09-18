import type {
  ActionResponse,
  PanelAuthRequest,
  PanelButtonStyleResponse,
  PanelButtonStyleSaveRequest,
  PanelCodeRequest,
  PanelGroupsResponse,
  PanelListResponse,
  PanelOptionsRequest,
  PanelOptionsResponse,
  PanelSaveRequest,
  PanelDetailSettingsResponse,
  PanelDetailSettingsSaveRequest,
  PanelStatusResponse,
  PanelTestResponse,
} from "../../types/panel";
import { panelPost } from "./client";

export function listPanels(body: PanelAuthRequest) {
  return panelPost<PanelListResponse>("/panels", body);
}

export function listPanelOptions(body: PanelOptionsRequest) {
  return panelPost<PanelOptionsResponse>("/panels/options", body);
}

export function savePanel(body: PanelSaveRequest) {
  return panelPost<ActionResponse>("/panels/save", body);
}

export function testPanel(body: PanelCodeRequest) {
  return panelPost<PanelTestResponse>("/panels/test", body);
}

export function deletePanel(body: PanelCodeRequest) {
  return panelPost<ActionResponse>("/panels/delete", body);
}

export function getPanelSettings(body: PanelCodeRequest) {
  return panelPost<PanelDetailSettingsResponse>("/panels/settings", body);
}

export function savePanelSettings(body: PanelDetailSettingsSaveRequest) {
  return panelPost<ActionResponse>("/panels/settings/save", body);
}

export function getPanelStatus(body: PanelCodeRequest) {
  return panelPost<PanelStatusResponse>("/panels/status", body);
}

export function getPanelGroups(body: PanelCodeRequest) {
  return panelPost<PanelGroupsResponse>("/panels/groups", body);
}

export function getPanelButtonStyle(body: PanelCodeRequest) {
  return panelPost<PanelButtonStyleResponse>("/panels/button-style", body);
}

export function savePanelButtonStyle(body: PanelButtonStyleSaveRequest) {
  return panelPost<ActionResponse>("/panels/button-style/save", body);
}
