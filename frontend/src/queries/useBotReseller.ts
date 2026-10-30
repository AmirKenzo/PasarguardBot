import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { QueryKey } from "@tanstack/react-query";
import { botResellerApi } from "../api/webapp";
import type { AuthPayload } from "../api/webapp";
import { useWebAppAuth } from "../hooks/useWebAppAuth";

const ROOT = "bot-reseller";

const STATE_REFRESH_MS = 15_000;
const USERS_REFRESH_MS = 60_000;

function useBotResellerQuery<TRes>(key: QueryKey, call: (auth: AuthPayload) => Promise<TRes>, enabled = true, refetchInterval?: number) {
  const { auth, ready } = useWebAppAuth();
  return useQuery({
    queryKey: [ROOT, ...(key as unknown[]), auth?.session_token, auth?.init_data],
    queryFn: () => call(auth as AuthPayload),
    enabled: ready && auth != null && enabled,
    refetchInterval,
  });
}

export function useBotResellerState(enabled = true) {
  return useBotResellerQuery(["state"], (auth) => botResellerApi.getState(auth), enabled, STATE_REFRESH_MS);
}

export function useBotResellerUsers(enabled: boolean) {
  return useBotResellerQuery(["users"], (auth) => botResellerApi.listUsers(auth), enabled, USERS_REFRESH_MS);
}

export function useBotResellerUser(id: number | null) {
  return useBotResellerQuery(["user", id], (auth) => botResellerApi.getUser({ ...auth, id: id as number }), id != null);
}

export function useBotResellerUsage(enabled: boolean) {
  return useBotResellerQuery(["usage"], (auth) => botResellerApi.getUsage(auth), enabled);
}

export function useBotResellerMutation<TVars extends object, TRes>(call: (body: TVars & AuthPayload) => Promise<TRes>) {
  const { auth } = useWebAppAuth();
  const queryClient = useQueryClient();
  return useMutation<TRes, Error, TVars>({
    mutationFn: (vars) => call({ ...vars, ...(auth as AuthPayload) }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [ROOT] });
      void queryClient.invalidateQueries({ queryKey: ["profile"] });
    },
  });
}
