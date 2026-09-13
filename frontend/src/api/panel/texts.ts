import type {
  ActionResponse,
  PanelTextDeleteRequest,
  PanelTextSaveRequest,
  PanelTextsRequest,
  PanelTextsResponse,
} from "../../types/panel";
import { panelPost } from "./client";

export function listTexts(body: PanelTextsRequest) {
  return panelPost<PanelTextsResponse>("/texts", body);
}

export function saveText(body: PanelTextSaveRequest) {
  return panelPost<ActionResponse>("/texts/save", body);
}

export function deleteText(body: PanelTextDeleteRequest) {
  return panelPost<ActionResponse>("/texts/delete", body);
}
