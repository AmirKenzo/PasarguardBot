/** Mirrors app/models/panel/panel_options.py */
import type { PagedRequest, PanelEnvelope, PageMeta } from "./common";

/** Never add secret-bearing columns here (password, cookie) — the backend
 * whitelists this exact same set and ignores anything else. */
export const PANEL_OPTION_FIELDS = ["code", "name", "enable", "base_url"] as const;

export interface PanelOptionsRequest extends PagedRequest {
  q?: string;
  /** Subset of PANEL_OPTION_FIELDS; defaults to ["code", "name"]. */
  fields?: string[];
}

export interface PanelOptionRow {
  code: number;
  name?: string | null;
  enable?: boolean | null;
  base_url?: string | null;
}

export interface PanelOptionsResponse extends PanelEnvelope {
  panels: PanelOptionRow[];
  meta: PageMeta;
}
