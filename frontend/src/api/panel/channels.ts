import type {
  ActionResponse,
  PanelAuthRequest,
  PanelChannelCreateRequest,
  PanelChannelDeleteRequest,
  PanelChannelsResponse,
  PanelLogChannelDeleteRequest,
  PanelLogChannelSaveRequest,
} from "../../types/panel";
import { panelPost } from "./client";

export function getChannels(body: PanelAuthRequest) {
  return panelPost<PanelChannelsResponse>("/channels", body);
}

export function createChannel(body: PanelChannelCreateRequest) {
  return panelPost<ActionResponse>("/channels/create", body);
}

export function deleteChannel(body: PanelChannelDeleteRequest) {
  return panelPost<ActionResponse>("/channels/delete", body);
}

export function saveLogChannel(body: PanelLogChannelSaveRequest) {
  return panelPost<ActionResponse>("/channels/logs/save", body);
}

export function deleteLogChannel(body: PanelLogChannelDeleteRequest) {
  return panelPost<ActionResponse>("/channels/logs/delete", body);
}
