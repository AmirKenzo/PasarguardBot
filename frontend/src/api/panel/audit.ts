import type { PanelAuditRequest, PanelAuditResponse } from "../../types/panel";
import { panelPost } from "./client";

export function listAudit(body: PanelAuditRequest) {
  return panelPost<PanelAuditResponse>("/audit", body);
}
