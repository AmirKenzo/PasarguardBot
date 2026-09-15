/** Mirrors app/models/panel/tools.py */
import type { PanelAuthRequest, PanelEnvelope, PanelOption } from "./common";

export interface PanelSystemMetrics {
  cpu_percent: number;
  cpu_cores: number;
  ram_percent: number;
  ram_used: number;
  ram_total: number;
  disk_percent: number;
  disk_used: number;
  disk_total: number;
  python?: string | null;
  platform?: string | null;
}

export interface PanelVersions {
  app?: string | null;
  telethon?: string | null;
  telethon_layer?: string | null;
  fastapi?: string | null;
  pasarguard?: string | null;
  database?: string | null;
}

export interface PanelScheduledJob {
  id: string;
  last_run?: string | null;
  next_run?: string | null;
}

export interface PanelToolsResponse extends PanelEnvelope {
  metrics: PanelSystemMetrics;
  versions: PanelVersions;
  jobs: PanelScheduledJob[];
  panels: PanelOption[];
  backup_supported: boolean;
}

/** `panel` is a panel code, or "all" for every panel. */
export interface PanelBulkIncreaseRequest extends PanelAuthRequest {
  panel?: string;
  volume_gb?: number | null;
  days?: number | null;
  confirm: boolean;
}
