/** Mirrors app/models/panel/keyboard.py */
import type { PanelAuthRequest, PanelEnvelope } from "./common";

/** "none" clears the built-in default colour; an empty value keeps it. */
export const STYLE_OPTIONS = ["", "primary", "success", "danger", "none"] as const;

export interface PanelKeyboardButton {
  key: string;
  section: string;
  title?: string | null;
  default_text?: string | null;
  text?: string | null;
  style?: string | null;
  default_icon?: number | null;
  icon?: number | null;
  hidden: boolean;
  in_home: boolean;
  /** Empty when the button can render; otherwise why the bot holds it back. */
  blocked: string;
}

export interface PanelKeyboardResponse extends PanelEnvelope {
  layout: string[][];
  buttons: PanelKeyboardButton[];
  home_keys: string[];
  sections: string[];
  style_options: string[];
  premium_emoji_enabled: boolean;
  /** Global switch: the home menu is drawn inside the chat, every button coloured. */
  glass_mode: boolean;
}

/** Rows of button keys, top to bottom. Empty rows are dropped. */
export interface PanelKeyboardLayoutRequest extends PanelAuthRequest {
  layout: string[][];
  hidden: string[];
}

export interface PanelKeyboardButtonSaveRequest extends PanelAuthRequest {
  key: string;
  text?: string;
  style?: string;
  icon?: string;
}

export interface PanelKeyboardIconClearRequest extends PanelAuthRequest {
  key: string;
}
