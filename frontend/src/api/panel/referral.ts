import type {
  ActionResponse,
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
