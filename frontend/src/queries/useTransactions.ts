import { useQuery } from "@tanstack/react-query";
import { transactionsApi } from "../api/webapp";
import { useWebAppAuth } from "../hooks/useWebAppAuth";

export function useTransactionsQuery(page: number, limit = 15) {
  const { auth, ready } = useWebAppAuth();

  return useQuery({
    queryKey: ["transactions", page, limit, auth?.session_token, auth?.init_data],
    queryFn: () => transactionsApi.getTransactions({ ...auth!, page, limit }),
    enabled: ready && auth != null,
  });
}

export function useRecentTransactionsQuery(limit = 5) {
  return useTransactionsQuery(1, limit);
}
