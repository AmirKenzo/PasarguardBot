import type {
  ActionResponse,
  PanelDiscountDeleteRequest,
  PanelDiscountSaveRequest,
  PanelDiscountsRequest,
  PanelDiscountsResponse,
} from "../../types/panel";
import { panelPost } from "./client";

export function listDiscounts(body: PanelDiscountsRequest) {
  return panelPost<PanelDiscountsResponse>("/discounts", body);
}

export function saveDiscount(body: PanelDiscountSaveRequest) {
  return panelPost<ActionResponse>("/discounts/save", body);
}

export function deleteDiscount(body: PanelDiscountDeleteRequest) {
  return panelPost<ActionResponse>("/discounts/delete", body);
}
