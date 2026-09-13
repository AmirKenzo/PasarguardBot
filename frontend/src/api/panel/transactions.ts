import type {
  ActionResponse,
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
