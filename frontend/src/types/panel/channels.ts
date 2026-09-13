/** Mirrors app/models/panel/channels.py */
import type { PanelAuthRequest, PanelEnvelope } from "./common";

export const DESTINATION_TYPES = ["channel", "supergroup"] as const;

export interface PanelChannelRow {
  id: number;
  title?: string | null;
  link?: string | null;
}

export interface PanelLogChannelRow {
  id: number;
  log_type: string;
  chat_id?: number | null;
  topic_id?: number | null;
  destination_type: string;
  is_active: boolean;
}

export interface PanelChannelsResponse extends PanelEnvelope {
  channels: PanelChannelRow[];
  log_channels: PanelLogChannelRow[];
  log_types: string[];
  destination_types: string[];
}

export interface PanelChannelCreateRequest extends PanelAuthRequest {
  channel_id: number;
  title: string;
  link: string;
}

export interface PanelChannelDeleteRequest extends PanelAuthRequest {
  channel_id: number;
}

export interface PanelLogChannelSaveRequest extends PanelAuthRequest {
  log_type: string;
  destination_type?: string;
  chat_id: number;
  topic_id?: number | null;
}

export interface PanelLogChannelDeleteRequest extends PanelAuthRequest {
  log_id: number;
}
