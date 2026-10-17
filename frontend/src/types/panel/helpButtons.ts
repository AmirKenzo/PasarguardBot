/** Mirrors app/models/panel/help_buttons.py */
import type { PanelAuthRequest, PanelEnvelope } from "./common";

export type HelpButtonKind = "link" | "app" | "text";

export interface PanelHelpTarget {
  id: string;
  button_text: string;
  button_style?: string | null;
  button_icon?: string | null;
  patterns: string[];
}

export interface PanelHelpButton {
  id: number;
  number: number;
  kind: HelpButtonKind;
  text: string;
  style?: string | null;
  icon?: string | null;
  url?: string | null;
  callback_key?: string | null;
  repo?: string | null;
  ios_url?: string | null;
  targets: PanelHelpTarget[];
  /** The app still runs on the old keyword categories. */
  legacy_categories: boolean;
  custom_message?: string | null;
}

export interface PanelHelpPreset {
  key: string;
  name: string;
  repo: string;
}

/** State of the "download latest releases into the log channel" run. */
export interface PanelHelpSync {
  running: boolean;
  last_summary?: string | null;
  log_channel_set: boolean;
}

export interface PanelHelpButtonsResponse extends PanelEnvelope {
  buttons: PanelHelpButton[];
  /** Rows of button ids, top to bottom. */
  layout: number[][];
  presets: PanelHelpPreset[];
  sync: PanelHelpSync;
  premium_emoji_enabled: boolean;
}

export interface PanelHelpLayoutRequest extends PanelAuthRequest {
  layout: number[][];
}

export interface PanelHelpButtonSaveRequest extends PanelAuthRequest {
  id?: number | null;
  kind: HelpButtonKind;
  text: string;
  style?: string;
  icon?: string;
  url?: string;
  repo?: string;
  ios_url?: string;
  targets?: PanelHelpTarget[];
  custom_message?: string;
}

export interface PanelHelpButtonSaveResponse extends PanelEnvelope {
  id?: number | null;
  message?: string | null;
}

export interface PanelHelpButtonIdRequest extends PanelAuthRequest {
  id: number;
}

export interface PanelHelpPresetsRequest extends PanelAuthRequest {
  keys: string[];
}

export interface PanelHelpReleaseRequest extends PanelAuthRequest {
  repo: string;
  targets: PanelHelpTarget[];
  refresh?: boolean;
}

export interface PanelHelpReleaseFile {
  name: string;
  size_mb: number;
  /** Target that would send this file; null when no pattern matches. */
  target_id?: string | null;
}

export interface PanelHelpReleaseResponse extends PanelEnvelope {
  tag: string;
  files: PanelHelpReleaseFile[];
  matches: Record<string, number>;
}

export interface PanelHelpVersion {
  tag: string;
  count: number;
  files: string[];
}

export interface PanelHelpVersionsResponse extends PanelEnvelope {
  versions: PanelHelpVersion[];
}

export interface PanelHelpVersionDeleteRequest extends PanelAuthRequest {
  id: number;
  /** Empty deletes every stored version. */
  tag: string;
}
