import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { balanceApi } from "../api/webapp";
import type { AuthPayload } from "../api/webapp/client";
import type {
  BalanceTonPaysInvoiceResponse,
  BalanceIrGatewayPaymentResponse,
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

export function useDepositAutoCardMutation() {
  const { auth } = useWebAppAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (amount: number) => balanceApi.depositAutoCard({ ...auth!, amount }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["profile"] });
      void queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
  });
}

const AUTO_CARD_STATUS_POLL_MS = 4000;

/** Polls one auto-card invoice's status while it's still pending; stops on paid/expired. */
export function useAutoCardStatusQuery(params: { orderId: number; amountIrt: number; createdAt: number } | null) {
  const { auth, ready } = useWebAppAuth();
  const queryClient = useQueryClient();

  return useQuery({
    queryKey: ["auto-card-status", params?.orderId],
    queryFn: async () => {
      const res = await balanceApi.getAutoCardStatus({
        ...auth!,
        order_id: params!.orderId,
        amount_irt: params!.amountIrt,
        created_at: params!.createdAt,
      });
      if (res.ok && res.status === "paid") {
        void queryClient.invalidateQueries({ queryKey: ["profile"] });
        void queryClient.invalidateQueries({ queryKey: ["transactions"] });
      }
      return res;
    },
    enabled: ready && auth != null && params != null,
    refetchInterval: (query) => (query.state.data?.status === "pending" ? AUTO_CARD_STATUS_POLL_MS : false),
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

export function useOpenIrGatewayPaymentQuery(gateway: string, enabled: boolean) {
  const { auth, ready } = useWebAppAuth();

  return useQuery({
    queryKey: ["ir-gateway-open", gateway],
    queryFn: () => balanceApi.getOpenIrGatewayPayment(auth!, gateway),
    enabled: enabled && ready && auth != null,
  });
}

function useIrGatewayAction<TArgs>(
  fn: (auth: AuthPayload, args: TArgs) => Promise<BalanceIrGatewayPaymentResponse>
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

export function useDepositIrGatewayMutation() {
  return useIrGatewayAction((auth, args: { gateway: string; amount: number }) =>
    balanceApi.depositIrGateway(auth, args.gateway, args.amount)
  );
}

export function useCheckIrGatewayMutation() {
  return useIrGatewayAction((auth, payment: number) => balanceApi.checkIrGatewayPayment(auth, payment));
}
