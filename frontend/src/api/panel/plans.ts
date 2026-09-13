import type {
  ActionResponse,
  PanelPlanDeleteRequest,
  PanelPlansRequest,
  PanelPlansResponse,
  PanelPlanSaveRequest,
} from "../../types/panel";
import { panelPost } from "./client";

export function listPlans(body: PanelPlansRequest) {
  return panelPost<PanelPlansResponse>("/plans", body);
}

export function savePlan(body: PanelPlanSaveRequest) {
  return panelPost<ActionResponse>("/plans/save", body);
}

export function deletePlan(body: PanelPlanDeleteRequest) {
  return panelPost<ActionResponse>("/plans/delete", body);
}
