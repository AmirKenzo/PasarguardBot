import type {
  ActionResponse,
  PanelServiceDeleteRequest,
  PanelServicesRequest,
  PanelServicesResponse,
  PanelServiceToggleRequest,
} from "../../types/panel";
import { panelPost } from "./client";

export function listServices(body: PanelServicesRequest) {
  return panelPost<PanelServicesResponse>("/services", body);
}

export function toggleService(body: PanelServiceToggleRequest) {
  return panelPost<ActionResponse>("/services/toggle", body);
}

export function deleteService(body: PanelServiceDeleteRequest) {
  return panelPost<ActionResponse>("/services/delete", body);
}
