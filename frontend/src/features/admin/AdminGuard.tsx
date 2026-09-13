import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ShieldAlert } from "lucide-react";
import { Button, Spinner } from "../../components/ui";
import { panelDashboardApi } from "../../api/panel";
import { usePanelQuery } from "../../queries/usePanelApi";
import { useTranslation } from "react-i18next";

/**
 * The backend is the authority on who is an admin: `/panel/me` answers only
 * for a user listed in ADMIN_ID. This just keeps non-admins from staring at
 * a shell full of failing requests.
 */
export function AdminGuard({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const { data, isLoading, isError, error, refetch } = usePanelQuery(
    ["me"],
    (auth) => panelDashboardApi.getMe(auth),
    { retry: false }
  );

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg">
        <Spinner size={28} className="text-primary" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-bg px-6 text-center">
        <ShieldAlert size={36} className="text-danger" />
        <div>
          <p className="font-medium text-text">{t("panel.guard.unavailable")}</p>
          <p className="mt-1 text-sm text-muted">{error?.message || t("panel.guard.notAdmin")}</p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="secondary" onClick={() => void refetch()}>
            {t("ui.retry")}
          </Button>
          <Link to="/">
            <Button size="sm" variant="ghost">
              {t("ui.back")}
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
