/** Mirrors app/models/panel/users.py */
import type { ActionResponse, PagedRequest, PageMeta, PanelAuthRequest, PanelEnvelope } from "./common";

export interface PanelUserRow {
  id: number;
  status?: string | null;
  blocked: boolean;
  number?: string | null;
  balance: number;
  joined_at?: number | null;
  services: number;
}

export interface PanelUsersRequest extends PagedRequest {
  q?: string;
  /** empty | active | blocked */
  state?: string;
}

export interface PanelUsersResponse extends PanelEnvelope {
  users: PanelUserRow[];
  meta: PageMeta;
}

export interface PanelUserServiceRow {
  code: number;
  username?: string | null;
  panel?: string | null;
  package_size?: number | null;
  expiration_time?: number | null;
  enable: boolean;
  is_test: boolean;
}

export interface PanelUserTransactionRow {
  id: number;
  amount: number;
  status?: string | null;
  created_at?: number | null;
}

export interface PanelUserDetailRequest extends PanelAuthRequest {
  user_id: number;
}

export interface PanelUserDetailResponse extends PanelEnvelope {
  user?: PanelUserRow | null;
  services: PanelUserServiceRow[];
  transactions: PanelUserTransactionRow[];
  referrals: number;
}

export interface PanelUserBalanceRequest extends PanelAuthRequest {
  user_id: number;
  /** Signed amount in toman. */
  delta: number;
  notify?: boolean;
}

export interface PanelUserBalanceResponse extends ActionResponse {
  balance?: number | null;
}

export interface PanelUserBlockRequest extends PanelAuthRequest {
  user_id: number;
  blocked: boolean;
  notify?: boolean;
}

export interface PanelUserPhoneRequest extends PanelAuthRequest {
  user_id: number;
  /** Empty clears the stored number. */
  phone: string;
}

export interface PanelUserPhoneResponse extends ActionResponse {
  number?: string | null;
}

export interface PanelUserMessageRequest extends PanelAuthRequest {
  user_id: number;
  text: string;
}
