import type { WebAppTransactionsRequest, WebAppTransactionsResponse } from "../../types/webapp";
import { apiPost } from "./client";

export function getTransactions(body: WebAppTransactionsRequest) {
  return apiPost<WebAppTransactionsResponse>("/transactions", body);
}
