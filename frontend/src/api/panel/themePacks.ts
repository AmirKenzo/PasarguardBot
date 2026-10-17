import type {
  ActionResponse,
  PanelAuthRequest,
  ThemePackApplyRequest,
  ThemePackApplyResponse,
  ThemePackCreateRequest,
  ThemePackCurrentRequest,
  ThemePackDetailResponse,
  ThemePackIdRequest,
  ThemePackOverviewResponse,
  ThemePackPreviewRequest,
  ThemePackPreviewResponse,
  ThemePackSaveRequest,
  ThemePackSaveResponse,
} from "../../types/panel";
import { panelPost } from "./client";

export function getOverview(body: PanelAuthRequest) {
  return panelPost<ThemePackOverviewResponse>("/theme-packs", body);
}

export function createFromCurrent(body: ThemePackCreateRequest) {
  return panelPost<ThemePackSaveResponse>("/theme-packs/create", body);
}

export function getPack(body: ThemePackIdRequest) {
  return panelPost<ThemePackDetailResponse>("/theme-packs/get", body);
}

export function savePack(body: ThemePackSaveRequest) {
  return panelPost<ThemePackSaveResponse>("/theme-packs/save", body);
}

export function deletePack(body: ThemePackIdRequest) {
  return panelPost<ActionResponse>("/theme-packs/delete", body);
}

export function sendPack(body: ThemePackIdRequest) {
  return panelPost<ActionResponse>("/theme-packs/send", body);
}

export function previewPack(body: ThemePackPreviewRequest) {
  return panelPost<ThemePackPreviewResponse>("/theme-packs/preview", body);
}

export function applyPack(body: ThemePackApplyRequest) {
  return panelPost<ThemePackApplyResponse>("/theme-packs/apply", body);
}

export function undoLastApply(body: PanelAuthRequest) {
  return panelPost<ActionResponse>("/theme-packs/undo", body);
}

export function currentValues(body: ThemePackCurrentRequest) {
  return panelPost<ThemePackDetailResponse>("/theme-packs/current", body);
}
