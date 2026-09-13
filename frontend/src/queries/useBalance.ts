import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { balanceApi } from "../api/webapp";
import type { CryptoCurrency } from "../types/webapp";
import { useWebAppAuth } from "../hooks/useWebAppAuth";

export function useBalanceMethodsQuery() {
  const { auth, ready } = useWebAppAuth();

  return useQuery({
    queryKey: ["balance-methods"],
    queryFn: () => balanceApi.getBalanceMethods(auth!),
    enabled: ready && auth != null,
  });
}

export function useRequestPhoneVerificationMutation() {
  const { auth } = useWebAppAuth();

  return useMutation({
    mutationFn: () => balanceApi.requestPhoneVerification(auth!),
  });
}

export function useDepositManualMutation() {
  const { auth } = useWebAppAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (amount: number) => balanceApi.depositManual({ ...auth!, amount }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["profile"] });
      void queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
  });
}

export function useDepositManualReceiptMutation() {
  const { auth } = useWebAppAuth();

  return useMutation({
    mutationFn: ({ txId, file }: { txId: number; file: File }) =>
      balanceApi.depositManualReceipt(auth!, txId, file),
  });
}

export function useDepositCryptoMutation() {
  const { auth } = useWebAppAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ amount, currency }: { amount: number; currency: CryptoCurrency }) =>
      balanceApi.depositCrypto({ ...auth!, amount, currency }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["profile"] });
      void queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
  });
}
