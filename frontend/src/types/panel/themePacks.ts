/** Mirrors app/models/panel/theme_pack.py and the pack layout in app/services/theme_pack.py */
import type { PanelAuthRequest, PanelEnvelope } from "./common";

export const THEME_PACK_FORMAT = "kenzo-theme-pack";

export interface ThemePackTextEntry {
  value: string;
}

export interface ThemePackButtonEntry {
  text?: string;
  /** primary | success | danger | none; older packs may still carry the retired glass style. */
  style?: string;
  /** Custom emoji id, as a string (it does not fit in a JS number). */
  icon?: string;
}

export interface ThemePackLayout {
  rows: string[][];
  hidden: string[];
}

export interface ThemePackData {
  format: string;
  version: number;
  name?: string;
  source?: { bot?: string; app_version?: string; created_at?: number | null };
  texts?: Record<string, Record<string, ThemePackTextEntry>>;
  buttons?: Record<string, ThemePackButtonEntry>;
  layout?: ThemePackLayout;
}

export interface ThemePackTextInfo {
  key: string;
  title: string;
  section: string;
  langs: string[];
  has_default: boolean;
  /** username | link | card_number | phone */
  hints: string[];
}

export interface ThemePackButtonInfo {
  key: string;
  title: string;
  section: string;
  customized: boolean;
  has_icon: boolean;
  hints: string[];
}

export interface ThemePackSection {
  key: string;
  name: string;
  icon: string;
}

export interface ThemePackImportInfo {
  id: number;
  pack_name: string;
  pack_id?: number | null;
  mode: string;
  created_at: number;
  restored: boolean;
  summary: { texts?: number; buttons?: number; layout?: boolean; reset?: number };
}

export interface ThemePackCounts {
  texts?: number;
  buttons?: number;
  layout?: number;
}

export interface ThemePackLibraryEntry {
  id: number;
  name: string;
  source_bot: string;
  created_at: number;
  updated_at: number;
  counts: ThemePackCounts;
  active: boolean;
}

export interface ThemePackOverviewResponse extends PanelEnvelope {
  packs: ThemePackLibraryEntry[];
  texts: ThemePackTextInfo[];
  buttons: ThemePackButtonInfo[];
  text_sections: ThemePackSection[];
  button_sections: string[];
  layout_customized: boolean;
  last_import?: ThemePackImportInfo | null;
}

export interface ThemePackCreateRequest extends PanelAuthRequest {
  name: string;
  text_keys: string[];
  button_keys: string[];
  include_layout: boolean;
  include_icons: boolean;
  include_defaults: boolean;
}

export interface ThemePackIdRequest extends PanelAuthRequest {
  pack_id: number;
}

export interface ThemePackSaveRequest extends PanelAuthRequest {
  pack_id?: number | null;
  name?: string;
  pack: ThemePackData;
  strict?: boolean;
}

export type ThemePackItemStatus = "new" | "changed" | "same" | "invalid" | "unknown";

export interface ThemePackItem {
  id: string;
  kind: "text" | "button" | "layout";
  key: string;
  lang?: string | null;
  title: string;
  section: string;
  status: ThemePackItemStatus;
  current?: string | null;
  incoming?: string | null;
  warnings: string[];
  errors: string[];
}

export interface ThemePackSaveResponse extends PanelEnvelope {
  message?: string | null;
  pack_id?: number | null;
  dropped: ThemePackItem[];
}

export interface ThemePackDetailResponse extends PanelEnvelope {
  message?: string | null;
  pack?: ThemePackLibraryEntry | null;
  data: ThemePackData;
  file_name: string;
}

/** A library pack (pack_id) or pack data from a file (pack). */
export interface ThemePackSource {
  pack_id?: number | null;
  pack?: ThemePackData | null;
}

export type ThemePackPreviewRequest = PanelAuthRequest & ThemePackSource;

export interface ThemePackPreviewResponse extends PanelEnvelope {
  message?: string | null;
  name: string;
  source: { bot?: string; app_version?: string; created_at?: number | null };
  items: ThemePackItem[];
}

export type ThemePackApplyMode = "merge" | "replace";

export interface ThemePackApplyRequest extends ThemePackPreviewRequest {
  /** Omitted applies every entry that differs from the bot. */
  item_ids?: string[] | null;
  mode: ThemePackApplyMode;
}

export interface ThemePackApplyResponse extends PanelEnvelope {
  message?: string | null;
  applied: number;
  reset: number;
  import_id?: number | null;
}

export interface ThemePackCurrentRequest extends PanelAuthRequest {
  text_keys: string[];
  button_keys: string[];
  include_layout?: boolean;
}
