/** Mirrors app/models/panel/common.py */

export interface PanelAuthRequest {
  session_token?: string | null;
  init_data?: string | null;
}

export interface PagedRequest extends PanelAuthRequest {
  page?: number;
  limit?: number;
}

export interface PanelEnvelope {
  ok: boolean;
  error?: string | null;
}

export interface PageMeta {
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

export interface ActionResponse extends PanelEnvelope {
  message?: string | null;
}

/** A panel the bot sells from, as offered in a picker. */
export interface PanelOption {
  code: number;
  name: string;
}

export const EMPTY_META: PageMeta = { total: 0, page: 1, limit: 25, total_pages: 0 };
