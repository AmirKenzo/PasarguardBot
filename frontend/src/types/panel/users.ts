/** Mirrors app/models/panel/users.py */
import type { ActionResponse, PagedRequest, PageMeta, PanelAuthRequest, PanelEnvelope } from "./common";

/** "active": normal. "banned": an admin blocked them (reversible by an
 * admin). "blocked_bot": the user blocked/stopped the bot themself — only
 * their own /start can undo it, not an admin action. "deleted": Telegram
 * reports the account itself was deleted. */
export type UserState = "active" | "banned" | "blocked_bot" | "deleted";

export interface PanelUserRow {
  id: number;
  status?: string | null;
  state: UserState;
  number?: string | null;
  balance: number;
  joined_at?: number | null;
  services: number;
}

export interface PanelUsersRequest extends PagedRequest {
  q?: string;
  /** empty | active | banned | blocked_bot | deleted */
  state?: string;
  /** newest | oldest */
  sort?: string;
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

export interface PanelTransferAdminsRequest extends PanelAuthRequest {
  user_id: number;
  panel_code: number;
}

export interface PanelTransferAdminRow {
  username: string;
  total_users: number;
  status?: string | null;
  note?: string | null;
  /** The admin's note or Telegram id matches this bot user. */
  suggested: boolean;
}

export interface PanelTransferAdminsResponse extends PanelEnvelope {
  /** The admin the bot is logged in as — the default destination. */
  current_admin?: string | null;
  admins: PanelTransferAdminRow[];
}

export interface PanelTransferPreviewRequest extends PanelAuthRequest {
  user_id: number;
  panel_code: number;
  source_admin: string;
  target_admin: string;
}

export interface PanelTransferConflictRow {
  username: string;
  owner_id: number;
}

export interface PanelTransferPreviewResponse extends PanelEnvelope {
  total_users: number;
  status_counts: Record<string, number>;
  active_users: number;
  will_create: number;
  already_linked: number;
  conflicts: PanelTransferConflictRow[];
  conflicts_total: number;
  active_used_traffic: number;
  active_data_limit: number;
  active_unlimited: number;
}

export interface PanelTransferStartRequest extends PanelTransferPreviewRequest {
  notify?: boolean;
}

export interface PanelTransferStartResponse extends ActionResponse {
  job_id?: string | null;
}

export interface PanelTransferStatusRequest extends PanelAuthRequest {
  job_id: string;
}

/** moved | moved_linked | moved_no_record | failed | conflict */
export type PanelTransferResult = "moved" | "moved_linked" | "moved_no_record" | "failed" | "conflict";

export interface PanelTransferResultRow {
  username: string;
  panel_user_id: number;
  result: PanelTransferResult;
  reason?: string | null;
  service_code?: number | null;
}

export interface PanelTransferStatusResponse extends PanelEnvelope {
  /** running | done | error */
  state: string;
  /** fetch | check | transfer | verify | done */
  phase: string;
  total: number;
  processed: number;
  skipped_inactive: number;
  remaining_active_on_source?: number | null;
  counts: Partial<Record<PanelTransferResult, number>>;
  source_admin?: string | null;
  target_admin?: string | null;
  panel_name?: string | null;
  job_error?: string | null;
  /** Filled only once the job has finished. */
  rows: PanelTransferResultRow[];
}
