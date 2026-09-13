/** Mirrors app/models/panel/broadcast.py */
import type { PanelAuthRequest, PanelEnvelope } from "./common";

export const TARGET_MODES = ["all", "active", "users_with_active_service"] as const;

export interface PanelBroadcastJobRow {
  id: number;
  text: string;
  target_mode: string;
  total_targets: number;
  sent_ok: number;
  sent_fail: number;
  status?: string | null;
  created_at?: number | null;
  can_pause: boolean;
  can_resume: boolean;
  can_cancel: boolean;
}

export interface PanelBroadcastResponse extends PanelEnvelope {
  jobs: PanelBroadcastJobRow[];
  target_modes: string[];
}

export interface PanelBroadcastSendRequest extends PanelAuthRequest {
  text: string;
  target_mode?: string;
  delay_ms?: number;
  batch_size?: number;
  batch_delay_ms?: number;
}

export interface PanelBroadcastJobRequest extends PanelAuthRequest {
  job_id: number;
}
