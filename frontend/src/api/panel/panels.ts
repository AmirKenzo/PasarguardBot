import type {
  ActionResponse,
  PanelAuthRequest,
  PanelCodeRequest,
  PanelListResponse,
  PanelSaveRequest,
} from "../../types/panel";
import { panelPost } from "./client";

export function listPanels(body: PanelAuthRequest) {
  return panelPost<PanelListResponse>("/panels", body);
}

export function savePanel(body: PanelSaveRequest) {
  return panelPost<ActionResponse>("/panels/save", body);
}

export function testPanel(body: PanelCodeRequest) {
  return panelPost<ActionResponse>("/panels/test", body);
}

export function deletePanel(body: PanelCodeRequest) {
  return panelPost<ActionResponse>("/panels/delete", body);
}
