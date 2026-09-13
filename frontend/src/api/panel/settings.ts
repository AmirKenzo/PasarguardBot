import type {
  ActionResponse,
  PanelAuthRequest,
  PanelSettingsResponse,
  PanelSettingsSaveRequest,
} from "../../types/panel";
import { panelPost } from "./client";

export function getSettings(body: PanelAuthRequest) {
  return panelPost<PanelSettingsResponse>("/settings", body);
}

export function saveSettings(body: PanelSettingsSaveRequest) {
  return panelPost<ActionResponse>("/settings/save", body);
}
