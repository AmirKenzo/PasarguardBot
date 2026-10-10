import type {
  ActionResponse,
  PanelAuthRequest,
  PanelCardActionRequest,
  PanelCardCreateRequest,
  PanelPaymentsResponse,
  PanelRuleCreateRequest,
  PanelRuleDeleteRequest,
  PanelRuleToggleRequest,
  PanelTonPaysResponse,
  PanelTonPaysSaveRequest,
  PanelTonPaysTestRequest,
  PanelWalletCreateRequest,
  PanelWalletDeleteRequest,
  PanelZarinpalResponse,
  PanelZarinpalSaveRequest,
  PanelZarinpalTestRequest,
  PanelZibalResponse,
  PanelZibalSaveRequest,
  PanelZibalTestRequest,
} from "../../types/panel";
import { panelPost } from "./client";

export function getPayments(body: PanelAuthRequest) {
  return panelPost<PanelPaymentsResponse>("/payments", body);
}

export function createWallet(body: PanelWalletCreateRequest) {
  return panelPost<ActionResponse>("/payments/wallets/create", body);
}

export function deleteWallet(body: PanelWalletDeleteRequest) {
  return panelPost<ActionResponse>("/payments/wallets/delete", body);
}

export function createCard(body: PanelCardCreateRequest) {
  return panelPost<ActionResponse>("/payments/cards/create", body);
}

export function activateCard(body: PanelCardActionRequest) {
  return panelPost<ActionResponse>("/payments/cards/activate", body);
}

export function deleteCard(body: PanelCardActionRequest) {
  return panelPost<ActionResponse>("/payments/cards/delete", body);
}

export function createRule(body: PanelRuleCreateRequest) {
  return panelPost<ActionResponse>("/payments/rules/create", body);
}

export function toggleRule(body: PanelRuleToggleRequest) {
  return panelPost<ActionResponse>("/payments/rules/toggle", body);
}

export function deleteRule(body: PanelRuleDeleteRequest) {
  return panelPost<ActionResponse>("/payments/rules/delete", body);
}

export function getTonPays(body: PanelAuthRequest) {
  return panelPost<PanelTonPaysResponse>("/payments/tonpays", body);
}

export function saveTonPays(body: PanelTonPaysSaveRequest) {
  return panelPost<ActionResponse>("/payments/tonpays/save", body);
}

export function testTonPays(body: PanelTonPaysTestRequest) {
  return panelPost<ActionResponse>("/payments/tonpays/test", body);
}

export function getZarinpal(body: PanelAuthRequest) {
  return panelPost<PanelZarinpalResponse>("/payments/zarinpal", body);
}

export function saveZarinpal(body: PanelZarinpalSaveRequest) {
  return panelPost<ActionResponse>("/payments/zarinpal/save", body);
}

export function testZarinpal(body: PanelZarinpalTestRequest) {
  return panelPost<ActionResponse>("/payments/zarinpal/test", body);
}

export function getZibal(body: PanelAuthRequest) {
  return panelPost<PanelZibalResponse>("/payments/zibal", body);
}

export function saveZibal(body: PanelZibalSaveRequest) {
  return panelPost<ActionResponse>("/payments/zibal/save", body);
}

export function testZibal(body: PanelZibalTestRequest) {
  return panelPost<ActionResponse>("/payments/zibal/test", body);
}
