/** Mirrors app/models/webapp/transactions.py */
import type { WebAppAuthRequest } from "./common";

export interface WebAppTransactionItem {
  id: string;
  type: string;
  amount: number;
  status: string;
  created_at: number;
  emoji: string;
}

export interface WebAppTransactionsRequest extends WebAppAuthRequest {
  page?: number;
  limit?: number;
}

export interface WebAppTransactionsResponse {
  ok: boolean;
  transactions: WebAppTransactionItem[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
  error?: string | null;
}
