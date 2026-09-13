import type { PanelAuthRequest, PanelDashboardResponse, PanelMeResponse } from "../../types/panel";
import { panelPost } from "./client";

export function getMe(body: PanelAuthRequest) {
  return panelPost<PanelMeResponse>("/me", body);
}

export function getDashboard(body: PanelAuthRequest) {
  return panelPost<PanelDashboardResponse>("/dashboard", body);
}
