import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { renewApi, servicesApi, upgradeApi, usageChartApi } from "../api/webapp";
import { useWebAppAuth } from "../hooks/useWebAppAuth";

export function useServicesQuery(page: number, limit: number, search: string, panelCode: number | null = null) {
  const { auth, ready } = useWebAppAuth();

  return useQuery({
    queryKey: ["services", auth?.session_token, auth?.init_data, page, limit, search, panelCode],
    queryFn: () =>
      servicesApi.getServices({
        ...auth!,
        page,
        limit,
        search: search.trim() || null,
        panel_code: panelCode,
      }),
    enabled: ready && auth != null,
  });
}

export function useServiceDetailQuery(code: number | null) {
  const { auth, ready } = useWebAppAuth();

  return useQuery({
    queryKey: ["service-detail", code, auth?.session_token, auth?.init_data],
    queryFn: () => servicesApi.getServiceDetail({ ...auth!, code: code! }),
    enabled: ready && auth != null && code != null && !Number.isNaN(code),
  });
}

export function useConfigLinksQuery(code: number, enabled: boolean) {
  const { auth, ready } = useWebAppAuth();

  return useQuery({
    queryKey: ["config-links", code, auth?.session_token, auth?.init_data],
    queryFn: () => servicesApi.getConfigLinks({ ...auth!, code }),
    enabled: ready && auth != null && enabled,
  });
}

export function useServiceClientsQuery(code: number, enabled: boolean) {
  const { auth, ready } = useWebAppAuth();

  return useQuery({
    queryKey: ["service-clients", code, auth?.session_token, auth?.init_data],
    queryFn: () => servicesApi.getServiceClients({ ...auth!, code }),
    enabled: ready && auth != null && enabled,
  });
}

export function useUsageChartQuery(code: number, days: number, enabled: boolean) {
  const { auth, ready } = useWebAppAuth();

  return useQuery({
    queryKey: ["usage-chart", code, days, auth?.session_token, auth?.init_data],
    queryFn: () => usageChartApi.getUsageChart({ ...auth!, code, days }),
    enabled: ready && auth != null && enabled,
  });
}

export function useChangeLinkMutation() {
  const { auth } = useWebAppAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (code: number) => servicesApi.changeLink({ ...auth!, code }),
    onSuccess: (_data, code) => {
      void queryClient.invalidateQueries({ queryKey: ["service-detail", code] });
    },
  });
}

export function useChangeSubscriptionMutation() {
  const { auth } = useWebAppAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (code: number) => servicesApi.changeSubscription({ ...auth!, code }),
    onSuccess: (_data, code) => {
      void queryClient.invalidateQueries({ queryKey: ["service-detail", code] });
    },
  });
}

export function useRenewOptionsQuery(code: number | null) {
  const { auth, ready } = useWebAppAuth();

  return useQuery({
    queryKey: ["renew-options", code, auth?.session_token, auth?.init_data],
    queryFn: () => renewApi.getRenewOptions({ ...auth!, code: code! }),
    enabled: ready && auth != null && code != null && !Number.isNaN(code),
  });
}

export function useRenewConfirmMutation() {
  const { auth } = useWebAppAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: { code: number; planId: number; discountCode?: string }) =>
      renewApi.confirmRenew({
        ...auth!,
        code: body.code,
        plan_id: body.planId,
        discount_code: body.discountCode?.trim() || null,
      }),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: ["service-detail", variables.code] });
      void queryClient.invalidateQueries({ queryKey: ["services"] });
      void queryClient.invalidateQueries({ queryKey: ["profile"] });
    },
  });
}

export function useExtendTimeOptionsQuery(code: number | null) {
  const { auth, ready } = useWebAppAuth();

  return useQuery({
    queryKey: ["extend-time-options", code, auth?.session_token, auth?.init_data],
    queryFn: () => upgradeApi.getExtendTimeOptions({ ...auth!, code: code! }),
    enabled: ready && auth != null && code != null && !Number.isNaN(code),
  });
}

export function useExtendTimeConfirmMutation() {
  const { auth } = useWebAppAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: { code: number; planId: number }) =>
      upgradeApi.confirmExtendTime({ ...auth!, code: body.code, plan_id: body.planId }),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: ["service-detail", variables.code] });
      void queryClient.invalidateQueries({ queryKey: ["services"] });
      void queryClient.invalidateQueries({ queryKey: ["profile"] });
    },
  });
}

export function useExtraVolumeOptionsQuery(code: number | null) {
  const { auth, ready } = useWebAppAuth();

  return useQuery({
    queryKey: ["extra-volume-options", code, auth?.session_token, auth?.init_data],
    queryFn: () => upgradeApi.getExtraVolumeOptions({ ...auth!, code: code! }),
    enabled: ready && auth != null && code != null && !Number.isNaN(code),
  });
}

export function useExtraVolumeConfirmMutation() {
  const { auth } = useWebAppAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: { code: number; planId: number }) =>
      upgradeApi.confirmExtraVolume({ ...auth!, code: body.code, plan_id: body.planId }),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: ["service-detail", variables.code] });
      void queryClient.invalidateQueries({ queryKey: ["services"] });
      void queryClient.invalidateQueries({ queryKey: ["profile"] });
    },
  });
}

export function useTransferConfigMutation() {
  const { auth } = useWebAppAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: { code: number; targetUserId: number }) =>
      upgradeApi.transferConfig({ ...auth!, code: body.code, target_user_id: body.targetUserId }),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: ["service-detail", variables.code] });
      void queryClient.invalidateQueries({ queryKey: ["services"] });
    },
  });
}
