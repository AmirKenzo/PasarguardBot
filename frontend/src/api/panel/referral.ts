import type {
  ActionResponse,
  PanelReferralPayoutSettleRequest,
  PanelReferralPayoutsRequest,
  PanelReferralPayoutsResponse,
  PanelReferralRequest,
  PanelReferralResponse,
  PanelReferralSaveRequest,
} from "../../types/panel";
import { panelPost } from "./client";

export function getReferral(body: PanelReferralRequest) {
  return panelPost<PanelReferralResponse>("/referral", body);
}

export function saveReferral(body: PanelReferralSaveRequest) {
  return panelPost<ActionResponse>("/referral/save", body);
}

export function getReferralPayouts(body: PanelReferralPayoutsRequest) {
  return panelPost<PanelReferralPayoutsResponse>("/referral/payouts", body);
}

export function settleReferralPayout(body: PanelReferralPayoutSettleRequest) {
  return panelPost<ActionResponse>("/referral/payouts/settle", body);
}
