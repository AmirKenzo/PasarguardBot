import type {
  ActionResponse,
  PanelAuthRequest,
  PanelResellerDeleteRequest,
  PanelResellerDetailRequest,
  PanelResellerDetailResponse,
  PanelResellerPlanDeleteRequest,
  PanelResellerPlansResponse,
  PanelResellerPlanSaveRequest,
  PanelResellersRequest,
  PanelResellersResponse,
  PanelResellerUpdateRequest,
} from "../../types/panel";
import { panelPost } from "./client";

export function listResellers(body: PanelResellersRequest) {
  return panelPost<PanelResellersResponse>("/resellers", body);
}

export function getReseller(body: PanelResellerDetailRequest) {
  return panelPost<PanelResellerDetailResponse>("/resellers/detail", body);
}

export function updateReseller(body: PanelResellerUpdateRequest) {
  return panelPost<ActionResponse>("/resellers/update", body);
}

export function deleteReseller(body: PanelResellerDeleteRequest) {
  return panelPost<ActionResponse>("/resellers/delete", body);
}

export function listResellerPlans(body: PanelAuthRequest) {
  return panelPost<PanelResellerPlansResponse>("/reseller-plans", body);
}

export function saveResellerPlan(body: PanelResellerPlanSaveRequest) {
  return panelPost<ActionResponse>("/reseller-plans/save", body);
}

export function deleteResellerPlan(body: PanelResellerPlanDeleteRequest) {
  return panelPost<ActionResponse>("/reseller-plans/delete", body);
}
