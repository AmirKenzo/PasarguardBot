/** Mirrors app/models/panel/texts.py */
import type { PanelAuthRequest, PanelEnvelope } from "./common";

export const BANNER_POSITIONS = ["", "top", "bottom"] as const;

/** One editable key: its definition plus the stored override, if any. */
export interface PanelTextEntry {
  key: string;
  title?: string | null;
  placeholders: Record<string, string>;
  value?: string | null;
  lang?: string | null;
  banner_url?: string | null;
  banner_position?: string | null;
  stored: boolean;
}

export interface PanelTextSection {
  key: string;
  name?: string | null;
  icon?: string | null;
  entries: PanelTextEntry[];
}

export interface PanelTextsRequest extends PanelAuthRequest {
  q?: string;
}

export interface PanelTextsResponse extends PanelEnvelope {
  sections: PanelTextSection[];
  banner_positions: string[];
}

export interface PanelTextSaveRequest extends PanelAuthRequest {
  key: string;
  value?: string;
  lang?: string;
  banner_url?: string;
  banner_position?: string;
}

export interface PanelTextDeleteRequest extends PanelAuthRequest {
  key: string;
  lang?: string;
}
