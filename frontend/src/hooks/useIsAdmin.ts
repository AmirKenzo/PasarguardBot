import { panelDashboardApi } from "../api/panel";
import { usePanelQuery } from "../queries/usePanelApi";

/**
 * Whether the signed-in user is a panel admin. Used only to decide whether to
 * show an entry point to the admin panel — `/panel` itself re-checks with the
 * backend regardless, so a false positive here can't grant access.
 */
export function useIsAdmin(): boolean {
  const { data, isError } = usePanelQuery(["me"], (auth) => panelDashboardApi.getMe(auth), {
    retry: false,
    staleTime: 60_000,
  });
  return !isError && !!data;
}
