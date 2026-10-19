import { AlertTriangle, Zap } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Button, Spinner } from "../../../components/ui";
import { panelHelpButtonsApi } from "../../../api/panel";
import type { PanelHelpSync } from "../../../types/panel";
import { usePanelAction } from "../../../queries/usePanelApi";
import { Hint } from "../keyboard/shared";
import { HELP_INVALIDATE } from "./shared";

export function SyncTab({ state }: { state: PanelHelpSync }) {
  const { t } = useTranslation();
  const sync = usePanelAction(panelHelpButtonsApi.runSync, { invalidate: HELP_INVALIDATE });

  return (
    <div className="space-y-4">
      {!state.log_channel_set && (
        <p className="flex items-start gap-1.5 rounded-md bg-warning/10 px-3 py-2 text-xs text-warning">
          <AlertTriangle size={13} className="mt-0.5 shrink-0" />
          <span>
            {t("panel.helpButtons.noLogChannel")}{" "}
            <Link to="/panel/channels" className="font-medium underline">
              {t("panel.common.channels")}
            </Link>
          </span>
        </p>
      )}

      <div className="space-y-3 rounded-sm border border-border bg-surface p-3 sm:p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-text">{t("panel.helpButtons.syncNow")}</h2>
          <Button
            size="sm"
            variant="secondary"
            disabled={state.running || !state.log_channel_set}
            loading={sync.isPending}
            onClick={() => sync.mutate({})}
          >
            <Zap size={14} />
            {t("panel.helpButtons.syncNow")}
          </Button>
        </div>
        <Hint>{t("panel.helpButtons.syncHint")}</Hint>
        {state.running && (
          <p className="flex items-center gap-2 text-xs text-primary">
            <Spinner size={13} />
            {t("panel.helpButtons.syncRunning")}
          </p>
        )}
        {state.last_summary && (
          <div className="whitespace-pre-line rounded-md bg-surface-2/60 p-3 text-xs leading-relaxed text-text">
            {/* The bot writes the summary in Telegram markdown; show it as plain text. */}
            {state.last_summary.replace(/\*\*/g, "")}
          </div>
        )}
      </div>
    </div>
  );
}
