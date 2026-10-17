import type {
  ActionResponse,
  PanelAuthRequest,
  PanelHelpButtonIdRequest,
  PanelHelpButtonSaveRequest,
  PanelHelpButtonSaveResponse,
  PanelHelpButtonsResponse,
  PanelHelpLayoutRequest,
  PanelHelpPresetsRequest,
  PanelHelpReleaseRequest,
  PanelHelpReleaseResponse,
  PanelHelpVersionDeleteRequest,
  PanelHelpVersionsResponse,
} from "../../types/panel";
import { panelPost } from "./client";

export function getHelpButtons(body: PanelAuthRequest) {
  return panelPost<PanelHelpButtonsResponse>("/help-buttons", body);
}

export function saveLayout(body: PanelHelpLayoutRequest) {
  return panelPost<ActionResponse>("/help-buttons/layout", body);
}

export function saveButton(body: PanelHelpButtonSaveRequest) {
  return panelPost<PanelHelpButtonSaveResponse>("/help-buttons/save", body);
}

export function deleteButton(body: PanelHelpButtonIdRequest) {
  return panelPost<ActionResponse>("/help-buttons/delete", body);
}

export function addPresets(body: PanelHelpPresetsRequest) {
  return panelPost<ActionResponse>("/help-buttons/presets", body);
}

export function releaseFiles(body: PanelHelpReleaseRequest) {
  return panelPost<PanelHelpReleaseResponse>("/help-buttons/release", body);
}

export function runSync(body: PanelAuthRequest) {
  return panelPost<ActionResponse>("/help-buttons/sync", body);
}

export function getVersions(body: PanelHelpButtonIdRequest) {
  return panelPost<PanelHelpVersionsResponse>("/help-buttons/versions", body);
}

export function deleteVersion(body: PanelHelpVersionDeleteRequest) {
  return panelPost<ActionResponse>("/help-buttons/versions/delete", body);
}
