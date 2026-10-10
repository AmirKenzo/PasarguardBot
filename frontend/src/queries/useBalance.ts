import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { balanceApi } from "../api/webapp";
import type { AuthPayload } from "../api/webapp/client";
import type {
  BalanceTonPaysInvoiceResponse,
  BalanceZarinpalPaymentResponse,
  BalanceZibalPaymentResponse,
  CryptoCurrency,
} from "../types/webapp";
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
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ amount, file }: { amount: number; file: File }) =>
      balanceApi.depositManualReceipt(auth!, amount, file),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["profile"] });
      void queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
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

export function useDepositStarsMutation() {
  const { auth, initData } = useWebAppAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (amount: number) =>
      balanceApi.depositStars({
        amount,
        session_token: auth?.session_token,
        // Always attach Telegram init_data when present so Stars credits the Mini App user.
        init_data: initData ?? auth?.init_data,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["profile"] });
      void queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
  });
}

export function useOpenTonPaysInvoiceQuery(enabled: boolean) {
  const { auth, ready } = useWebAppAuth();

  return useQuery({
    queryKey: ["tonpays-open"],
    queryFn: () => balanceApi.getOpenTonPaysInvoice(auth!),
    enabled: enabled && ready && auth != null,
  });
}

function useTonPaysAction<TArgs>(
  fn: (auth: AuthPayload, args: TArgs) => Promise<BalanceTonPaysInvoiceResponse>
) {
  const { auth } = useWebAppAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (args: TArgs) => fn(auth!, args),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["profile"] });
      void queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
  });
}

export function useDepositTonPaysMutation() {
  return useTonPaysAction((auth, amount: number) => balanceApi.depositTonPays(auth, amount));
}

export function useCheckTonPaysMutation() {
  return useTonPaysAction((auth, invoice: number) => balanceApi.checkTonPaysInvoice(auth, invoice));
}

export function useChangeTonPaysCardMutation() {
  return useTonPaysAction((auth, invoice: number) => balanceApi.changeTonPaysCard(auth, invoice));
}

export function useSendTonPaysReceiptMutation() {
  return useTonPaysAction((auth, args: { invoice: number; file: File }) =>
    balanceApi.sendTonPaysReceipt(auth, args.invoice, args.file)
  );
}

export function useOpenZarinpalPaymentQuery(enabled: boolean) {
  const { auth, ready } = useWebAppAuth();

  return useQuery({
    queryKey: ["zarinpal-open"],
    queryFn: () => balanceApi.getOpenZarinpalPayment(auth!),
    enabled: enabled && ready && auth != null,
  });
}

function useZarinpalAction<TArgs>(
  fn: (auth: AuthPayload, args: TArgs) => Promise<BalanceZarinpalPaymentResponse>
) {
  const { auth } = useWebAppAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (args: TArgs) => fn(auth!, args),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["profile"] });
      void queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
  });
}

export function useDepositZarinpalMutation() {
  return useZarinpalAction((auth, amount: number) => balanceApi.depositZarinpal(auth, amount));
}

export function useCheckZarinpalMutation() {
  return useZarinpalAction((auth, payment: number) => balanceApi.checkZarinpalPayment(auth, payment));
}

export function useOpenZibalPaymentQuery(enabled: boolean) {
  const { auth, ready } = useWebAppAuth();

  return useQuery({
    queryKey: ["zibal-open"],
    queryFn: () => balanceApi.getOpenZibalPayment(auth!),
    enabled: enabled && ready && auth != null,
  });
}

function useZibalAction<TArgs>(fn: (auth: AuthPayload, args: TArgs) => Promise<BalanceZibalPaymentResponse>) {
  const { auth } = useWebAppAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (args: TArgs) => fn(auth!, args),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["profile"] });
      void queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
  });
}

export function useDepositZibalMutation() {
  return useZibalAction((auth, amount: number) => balanceApi.depositZibal(auth, amount));
}

export function useCheckZibalMutation() {
  return useZibalAction((auth, payment: number) => balanceApi.checkZibalPayment(auth, payment));
}
