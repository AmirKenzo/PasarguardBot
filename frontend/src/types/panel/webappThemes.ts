/** Mirrors app/models/panel/webapp_theme.py */
import type { WebappTheme } from "../../design/webappThemes";
import type { PanelAuthRequest, PanelEnvelope } from "./common";

export type WebappThemeMode = "telegram" | "custom";

export interface WebappThemeEntry {
  id: number;
  name: string;
  source_bot: string;
  imported: boolean;
  created_at: number;
  updated_at: number;
  theme: WebappTheme;
}

export interface WebappThemeOverviewResponse extends PanelEnvelope {
  mode: WebappThemeMode;
  /** "custom:<id>" for a library theme, otherwise a preset id. */
  active: string;
  user_scheme: boolean;
  user_pick: boolean;
  themes: WebappThemeEntry[];
  max_themes: number;
}

export interface WebappThemeIdRequest extends PanelAuthRequest {
  theme_id: number;
}

export interface WebappThemeSaveRequest extends PanelAuthRequest {
  theme_id?: number | null;
  name: string;
  theme: WebappTheme;
  source_bot?: string;
  imported?: boolean;
}

export interface WebappThemeSaveResponse extends PanelEnvelope {
  message?: string | null;
  theme_id?: number | null;
}

export interface WebappThemeActivateRequest extends PanelAuthRequest {
  active: string;
  theme?: WebappTheme | null;
}

export interface WebappThemeOptionsRequest extends PanelAuthRequest {
  mode?: WebappThemeMode;
  user_scheme?: boolean;
  user_pick?: boolean;
}

export interface WebappThemeSharePack {
  format: string;
  version: number;
  name?: string;
  source?: { bot?: string; app_version?: string; created_at?: number | null };
  webapp?: unknown;
}

export interface WebappThemeShareResponse extends PanelEnvelope {
  data: WebappThemeSharePack;
  file_name: string;
}
