import type {
  ActionResponse,
  PanelAuthRequest,
  PanelBroadcastJobRequest,
  PanelBroadcastResponse,
  PanelBroadcastSendRequest,
} from "../../types/panel";
import { panelPost } from "./client";

export function getBroadcast(body: PanelAuthRequest) {
  return panelPost<PanelBroadcastResponse>("/broadcast", body);
}

export function send(body: PanelBroadcastSendRequest) {
  return panelPost<ActionResponse>("/broadcast/send", body);
}

export function pause(body: PanelBroadcastJobRequest) {
  return panelPost<ActionResponse>("/broadcast/pause", body);
}

export function resume(body: PanelBroadcastJobRequest) {
  return panelPost<ActionResponse>("/broadcast/resume", body);
}

export function cancel(body: PanelBroadcastJobRequest) {
  return panelPost<ActionResponse>("/broadcast/cancel", body);
}
