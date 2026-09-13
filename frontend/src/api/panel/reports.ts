import type { PanelReportsRequest, PanelReportsResponse } from "../../types/panel";
import { panelPost } from "./client";

export function getReports(body: PanelReportsRequest) {
  return panelPost<PanelReportsResponse>("/reports", body);
}
