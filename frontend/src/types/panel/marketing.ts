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
  referral_bonus_amount: number;
  referral_banner_text?: string | null;
}

export interface PanelReferralRewardRow {
  id: number;
  referrer_id?: number | null;
  referred_id?: number | null;
  reward_amount: number;
  bonus_amount: number;
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
  referral_bonus_amount: number;
  referral_banner_text?: string;
}
