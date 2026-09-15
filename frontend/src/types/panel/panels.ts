/** Mirrors app/models/panel/panels.py */
import type { PanelAuthRequest, PanelEnvelope } from "./common";

export const AUTH_TYPES = ["password", "api_key"] as const;

export interface PanelRow {
  code: number;
  name: string;
  base_url: string;
  tunnel_url?: string | null;
  username?: string | null;
  auth_type: string;
  enable: boolean;
  test_enabled: boolean;
  test_volume_gb: number;
  test_duration_days: number;
}

export interface PanelListResponse extends PanelEnvelope {
  panels: PanelRow[];
  auth_types: string[];
}

/** Creates when `code` is null, otherwise updates that panel.
 *  On update an empty `secret` keeps the stored credential. */
export interface PanelSaveRequest extends PanelAuthRequest {
  code?: number | null;
  name: string;
  base_url: string;
  tunnel_url?: string;
  auth_type?: string;
  username?: string;
  secret?: string;
  enable?: boolean;
  test_enabled?: boolean;
  test_volume_gb?: number;
  test_duration_days?: number;
}

export interface PanelCodeRequest extends PanelAuthRequest {
  code: number;
}
