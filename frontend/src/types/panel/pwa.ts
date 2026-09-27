/** Mirrors app/models/panel/pwa.py */
import type { ActionResponse, PanelAuthRequest, PanelEnvelope } from "./common";

export interface PwaSettingsResponse extends PanelEnvelope {
  app_name: string;
  short_name: string;
  description: string;
  has_custom_icon: boolean;
  icon_version: number;
}

export interface PwaSettingsSaveRequest extends PanelAuthRequest {
  app_name: string;
  short_name: string;
  description: string;
}

export interface PwaIconUploadResponse extends ActionResponse {
  icon_version: number;
}
