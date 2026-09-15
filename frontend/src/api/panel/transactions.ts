import type {
  ActionResponse,
  PanelReceiptLinkRequest,
  PanelReceiptLinkResponse,
  PanelTransactionActionRequest,
  PanelTransactionsRequest,
  PanelTransactionsResponse,
} from "../../types/panel";
import { panelPost } from "./client";

export function listTransactions(body: PanelTransactionsRequest) {
  return panelPost<PanelTransactionsResponse>("/transactions", body);
}

export function approve(body: PanelTransactionActionRequest) {
  return panelPost<ActionResponse>("/transactions/approve", body);
}

export function reject(body: PanelTransactionActionRequest) {
  return panelPost<ActionResponse>("/transactions/reject", body);
}

export function requestFix(body: PanelTransactionActionRequest) {
  return panelPost<ActionResponse>("/transactions/request-fix", body);
}

export function reportMismatch(body: PanelTransactionActionRequest) {
  return panelPost<ActionResponse>("/transactions/report-mismatch", body);
}

export function receiptLink(body: PanelReceiptLinkRequest) {
  return panelPost<PanelReceiptLinkResponse>("/transactions/receipt-link", body);
}
