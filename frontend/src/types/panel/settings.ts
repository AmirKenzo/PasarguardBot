/** Mirrors app/models/panel/settings.py */
import type { PanelAuthRequest, PanelEnvelope } from "./common";

export type PanelSettingValue = boolean | number | null;

/** One setting, described well enough for the client to render it. */
export interface PanelSettingField {
  key: string;
  /** bool | number */
  type: string;
  default: PanelSettingValue;
  value: PanelSettingValue;
}

export interface PanelSettingSection {
  key: string;
  fields: PanelSettingField[];
}

export interface PanelSettingsResponse extends PanelEnvelope {
  sections: PanelSettingSection[];
  initialized: boolean;
}

/** Only keys present in the section defaults are written; the rest are dropped. */
export interface PanelSettingsSaveRequest extends PanelAuthRequest {
  values: Record<string, PanelSettingValue>;
}
