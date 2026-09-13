import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { QueryKey, UseQueryOptions } from "@tanstack/react-query";
import type { AuthPayload } from "../api/panel";
import { useWebAppAuth } from "../hooks/useWebAppAuth";
import { useToast } from "../components/ui/Toast";

/** Every admin panel query is "call this endpoint with the WebApp credentials". */
export function usePanelQuery<TRes>(
  key: QueryKey,
  call: (auth: AuthPayload) => Promise<TRes>,
  options?: Omit<UseQueryOptions<TRes, Error, TRes, QueryKey>, "queryKey" | "queryFn">
) {
  const { auth, ready } = useWebAppAuth();

  return useQuery<TRes, Error, TRes, QueryKey>({
    queryKey: ["panel", ...(key as unknown[])],
    queryFn: () => call(auth as AuthPayload),
    ...options,
    enabled: ready && (options?.enabled ?? true),
  });
}

export interface PanelActionOptions {
  /** Query key prefixes to refetch once the action succeeds. */
  invalidate?: QueryKey[];
  /** Shown as a toast when the endpoint returns no message of its own. */
  successMessage?: string;
}

/**
 * A state-changing panel call: shows the backend's message as a toast,
 * surfaces errors the same way, and refreshes whatever the change affected.
 */
export function usePanelAction<TVars, TRes extends { message?: string | null }>(
  call: (vars: TVars & AuthPayload) => Promise<TRes>,
  { invalidate = [], successMessage }: PanelActionOptions = {}
) {
  const { auth } = useWebAppAuth();
  const queryClient = useQueryClient();
  const toast = useToast();

  return useMutation<TRes, Error, TVars>({
    mutationFn: (vars: TVars) => call({ ...(vars as object), ...(auth || {}) } as TVars & AuthPayload),
    onSuccess: (result) => {
      const message = result?.message || successMessage;
      if (message) toast.show(message, "success");
      for (const key of invalidate) {
        void queryClient.invalidateQueries({ queryKey: ["panel", ...(key as unknown[])] });
      }
    },
    onError: (error) => {
      toast.show(error.message || "عملیات انجام نشد", "error");
    },
  });
}
