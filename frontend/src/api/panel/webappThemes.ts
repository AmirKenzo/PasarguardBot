import type {
  ActionResponse,
  PanelAuthRequest,
  WebappThemeActivateRequest,
  WebappThemeIdRequest,
  WebappThemeOptionsRequest,
  WebappThemeOverviewResponse,
  WebappThemeSaveRequest,
  WebappThemeSaveResponse,
  WebappThemeShareResponse,
} from "../../types/panel";
import { panelPost } from "./client";

export function getOverview(body: PanelAuthRequest) {
  return panelPost<WebappThemeOverviewResponse>("/webapp-themes", body);
}

export function saveTheme(body: WebappThemeSaveRequest) {
  return panelPost<WebappThemeSaveResponse>("/webapp-themes/save", body);
}

export function deleteTheme(body: WebappThemeIdRequest) {
  return panelPost<ActionResponse>("/webapp-themes/delete", body);
}

export function activateTheme(body: WebappThemeActivateRequest) {
  return panelPost<ActionResponse>("/webapp-themes/activate", body);
}

export function updateOptions(body: WebappThemeOptionsRequest) {
  return panelPost<ActionResponse>("/webapp-themes/options", body);
}

export function shareTheme(body: WebappThemeIdRequest) {
  return panelPost<WebappThemeShareResponse>("/webapp-themes/share", body);
}

export function sendTheme(body: WebappThemeIdRequest) {
  return panelPost<ActionResponse>("/webapp-themes/send", body);
}
