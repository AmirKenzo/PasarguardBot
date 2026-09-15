import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { buyApi } from "../api/webapp";
import { useWebAppAuth } from "../hooks/useWebAppAuth";

export function useBuyOptionsQuery() {
  const { auth, ready } = useWebAppAuth();

  return useQuery({
    queryKey: ["buy-options", auth?.session_token, auth?.init_data],
    queryFn: () => buyApi.getBuyOptions(auth!),
    enabled: ready && auth != null,
  });
}

export function useBuyPlansQuery(panelCode: number | null, duration?: number | null) {
  const { auth, ready } = useWebAppAuth();

  return useQuery({
    queryKey: ["buy-plans", panelCode, duration, auth?.session_token, auth?.init_data],
    queryFn: () =>
      buyApi.getBuyPlans({
        ...auth!,
        panel_code: panelCode!,
        duration: duration ?? null,
      }),
    enabled: ready && auth != null && panelCode != null,
  });
}

export function useGenerateBuyUsernameMutation() {
  const { auth } = useWebAppAuth();

  return useMutation({
    mutationFn: (panelCode: number) => buyApi.generateBuyUsername({ ...auth!, panel_code: panelCode }),
  });
}

export function useBuyPreviewMutation() {
  const { auth } = useWebAppAuth();

  return useMutation({
    mutationFn: (body: { panelCode: number; planId: number; username: string; discountCode?: string }) =>
      buyApi.previewBuy({
        ...auth!,
        panel_code: body.panelCode,
        plan_id: body.planId,
        username: body.username.trim(),
        discount_code: body.discountCode?.trim() || null,
      }),
  });
}

export function useBuyConfirmMutation() {
  const { auth } = useWebAppAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: { panelCode: number; planId: number; username: string; discountCode?: string }) =>
      buyApi.confirmBuy({
        ...auth!,
        panel_code: body.panelCode,
        plan_id: body.planId,
        username: body.username.trim(),
        discount_code: body.discountCode?.trim() || null,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["profile"] });
      void queryClient.invalidateQueries({ queryKey: ["services"] });
    },
  });
}
