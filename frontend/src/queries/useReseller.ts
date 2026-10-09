import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { QueryKey } from "@tanstack/react-query";
import { resellerApi } from "../api/webapp";
import type { AuthPayload } from "../api/webapp";
import { useWebAppAuth } from "../hooks/useWebAppAuth";

/** Every reseller query key starts here, so one invalidation refreshes lists, details and history. */
const ROOT = "reseller";

function useResellerQuery<TRes>(key: QueryKey, call: (auth: AuthPayload) => Promise<TRes>, enabled = true) {
  const { auth, ready } = useWebAppAuth();
  return useQuery({
    queryKey: [ROOT, ...(key as unknown[]), auth?.session_token, auth?.init_data],
    queryFn: () => call(auth as AuthPayload),
    enabled: ready && auth != null && enabled,
  });
}

export function useResellerBuyOptions() {
  return useResellerQuery(["buy-options"], (auth) => resellerApi.getBuyOptions(auth));
}

export function useResellerAccounts(enabled = true) {
  return useResellerQuery(["accounts"], (auth) => resellerApi.listAccounts(auth), enabled);
}

export function useResellerAccount(code: number | null) {
  return useResellerQuery(["account", code], (auth) => resellerApi.getAccount({ ...auth, code: code as number }), code != null);
}

export function useResellerUsage(code: number, page: number, enabled: boolean) {
  return useResellerQuery(
    ["usage", code, page],
    (auth) => resellerApi.getUsage({ ...auth, code, page, limit: 15 }),
    enabled
  );
}

export function useResellerEvents(code: number, page: number, enabled: boolean) {
  return useResellerQuery(
    ["events", code, page],
    (auth) => resellerApi.getEvents({ ...auth, code, page, limit: 15 }),
    enabled
  );
}

/**
 * A reseller call made with the WebApp credentials. ``refresh`` (default) reloads every
 * reseller query and the profile balance after success; previews pass ``refresh: false``.
 */
export function useResellerMutation<TVars extends object, TRes>(
  call: (body: TVars & AuthPayload) => Promise<TRes>,
  { refresh = true }: { refresh?: boolean } = {}
) {
  const { auth } = useWebAppAuth();
  const queryClient = useQueryClient();
  return useMutation<TRes, Error, TVars>({
    mutationFn: (vars) => call({ ...vars, ...(auth as AuthPayload) }),
    onSuccess: () => {
      if (!refresh) return;
      void queryClient.invalidateQueries({ queryKey: [ROOT] });
      void queryClient.invalidateQueries({ queryKey: ["profile"] });
    },
  });
}
