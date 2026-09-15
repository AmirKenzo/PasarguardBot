import type {
  ActionResponse,
  PanelAuthRequest,
  PanelBulkIncreaseRequest,
  PanelToolsResponse,
} from "../../types/panel";
import { panelPost } from "./client";

export function getTools(body: PanelAuthRequest) {
  return panelPost<PanelToolsResponse>("/tools", body);
}

export function backupToLogChannel(body: PanelAuthRequest) {
  return panelPost<ActionResponse>("/tools/backup/send", body);
}

export function backupToMe(body: PanelAuthRequest) {
  return panelPost<ActionResponse>("/tools/backup/send-to-me", body);
}

export function bulkIncrease(body: PanelBulkIncreaseRequest) {
  return panelPost<ActionResponse>("/tools/bulk-increase", body);
}
