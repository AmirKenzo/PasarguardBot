import type {
  ActionResponse,
  PanelAuthRequest,
  PanelKeyboardButtonSaveRequest,
  PanelKeyboardIconClearRequest,
  PanelKeyboardLayoutRequest,
  PanelKeyboardResponse,
} from "../../types/panel";
import { panelPost } from "./client";

export function getKeyboard(body: PanelAuthRequest) {
  return panelPost<PanelKeyboardResponse>("/keyboard", body);
}

export function saveLayout(body: PanelKeyboardLayoutRequest) {
  return panelPost<ActionResponse>("/keyboard/layout", body);
}

export function resetLayout(body: PanelAuthRequest) {
  return panelPost<ActionResponse>("/keyboard/layout/reset", body);
}

export function saveButton(body: PanelKeyboardButtonSaveRequest) {
  return panelPost<ActionResponse>("/keyboard/button", body);
}

export function clearIcon(body: PanelKeyboardIconClearRequest) {
  return panelPost<ActionResponse>("/keyboard/icon-clear", body);
}
