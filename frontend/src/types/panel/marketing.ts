/** Mirrors app/models/panel/marketing.py */
import type { PagedRequest, PageMeta, PanelAuthRequest, PanelEnvelope } from "./common";

export const DISCOUNT_CODE_PATTERN = /^[A-Za-z0-9_-]{2,40}$/;

export interface PanelDiscountRow {
  id: number;
  code: string;
  discount_percentage: number;
  usage_limit: number;
  times_used: number;
  expiration_date?: number | null;
  user_id?: number | null;
  is_public: boolean;
  expired: boolean;
  exhausted: boolean;
}

export type PanelDiscountsRequest = PagedRequest;

export interface PanelDiscountsResponse extends PanelEnvelope {
  discounts: PanelDiscountRow[];
  meta: PageMeta;
}

export interface PanelDiscountSaveRequest extends PanelAuthRequest {
  code_id?: number | null;
  code: string;
  discount_percentage: number;
  usage_limit?: number;
  /** Null means no expiry. */
  expires_days?: number | null;
  /** Null means the code is public. */
  user_id?: number | null;
  is_public?: boolean;
}

export interface PanelDiscountDeleteRequest extends PanelAuthRequest {
  code_id: number;
}

export interface PanelReferralSettings {
  referral_enabled: boolean;
  referral_reward_amount: number;
  referral_reward_mode: "fixed" | "percent";
  referral_reward_percent: number;
  referral_reward_max: number;
  referral_bonus_amount: number;
  referral_bonus_mode: "fixed" | "percent";
  referral_bonus_percent: number;
  referral_bonus_max: number;
  /** "wallet" credits the reward at once; "earnings" keeps it apart, withdrawable. */
  referral_reward_destination: "wallet" | "earnings";
  referral_withdraw_enabled: boolean;
  referral_withdraw_min: number;
  referral_transfer_enabled: boolean;
  referral_banner_text?: string | null;
}

export interface PanelReferralRewardRow {
  id: number;
  referrer_id?: number | null;
  referred_id?: number | null;
  reward_amount: number;
  bonus_amount: number;
  base_amount?: number | null;
  reward_percent?: number | null;
  bonus_percent?: number | null;
  status?: string | null;
  created_at?: number | null;
}

export type PanelReferralRequest = PagedRequest;

export interface PanelReferralResponse extends PanelEnvelope {
  settings: PanelReferralSettings;
  rewards: PanelReferralRewardRow[];
  meta: PageMeta;
  total_rewarded: number;
  total_paid: number;
  total_bonus: number;
}

export interface PanelReferralSaveRequest extends PanelAuthRequest {
  referral_enabled: boolean;
  referral_reward_amount: number;
  referral_reward_mode: "fixed" | "percent";
  referral_reward_percent: number;
  referral_reward_max: number;
  referral_bonus_amount: number;
  referral_bonus_mode: "fixed" | "percent";
  referral_bonus_percent: number;
  referral_bonus_max: number;
  referral_reward_destination: "wallet" | "earnings";
  referral_withdraw_enabled: boolean;
  referral_withdraw_min: number;
  referral_transfer_enabled: boolean;
  referral_banner_text?: string;
}

/** Mirrors PanelReferralPayoutRow: a referrer cashing out (card, reviewed) or moving earnings to the wallet. */
export interface PanelReferralPayoutRow {
  id: number;
  user_id: number;
  amount: number;
  method: "card" | "wallet" | string;
  status: "pending" | "paid" | "rejected" | "completed" | string;
  card_number?: string | null;
  card_holder?: string | null;
  admin_id?: number | null;
  admin_note?: string | null;
  created_at?: number | null;
  reviewed_at?: number | null;
}

export interface PanelReferralPayoutsRequest extends PagedRequest {
  status?: string;
}

export interface PanelReferralPayoutsResponse extends PanelEnvelope {
  payouts: PanelReferralPayoutRow[];
  meta: PageMeta;
  pending_count: number;
}

export interface PanelReferralPayoutSettleRequest extends PanelAuthRequest {
  id: number;
  paid: boolean;
  note?: string;
}
