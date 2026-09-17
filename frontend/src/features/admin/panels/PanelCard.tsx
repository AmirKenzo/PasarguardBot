import { useState } from "react";
import { Activity, Eye, Gift, Globe, KeyRound, Lock, Pencil, Settings, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Card } from "../../../components/ui";
import { ConfirmButton } from "../components";
import { panelPanelsApi } from "../../../api/panel";
import type { PanelRow } from "../../../types/panel";
import { usePanelAction } from "../../../queries/usePanelApi";

const ACCENTS = [
  { bg: "rgba(96,165,250,0.14)", border: "rgba(96,165,250,0.3)" },
  { bg: "rgba(251,191,36,0.14)", border: "rgba(251,191,36,0.3)" },
  { bg: "rgba(167,139,250,0.14)", border: "rgba(167,139,250,0.3)" },
  { bg: "rgba(244,114,182,0.14)", border: "rgba(244,114,182,0.3)" },
  { bg: "rgba(148,163,184,0.12)", border: "rgba(148,163,184,0.25)" },
];

const DEFAULT_ACCENT = ACCENTS[0]!;

function accentFor(code: number) {
  return ACCENTS[code % ACCENTS.length] ?? DEFAULT_ACCENT;
}

const iconButtonClass =
  "flex h-8 w-8 items-center justify-center rounded-md border border-border text-muted transition-colors hover:border-primary/40 hover:bg-primary/10 hover:text-primary";

export interface PanelCardProps {
  panel: PanelRow;
  trialEnabled?: boolean;
  onView: () => void;
  onEdit: () => void;
  onSettings: () => void;
}

export function PanelCard({ panel, trialEnabled, onView, onEdit, onSettings }: PanelCardProps) {
  const { t } = useTranslation();
  const [pingMs, setPingMs] = useState<number | null>(null);
  const accent = accentFor(panel.code);

  const test = usePanelAction(panelPanelsApi.testPanel);
  const remove = usePanelAction(panelPanelsApi.deletePanel, {
    invalidate: [["panels"], ["plans"], ["dashboard"]],
  });

  const handleTest = () => {
    setPingMs(null);
    test.mutate(
      { code: panel.code },
      {
        onSuccess: (result) => {
          if (typeof result.latency_ms === "number") setPingMs(result.latency_ms);
        },
      }
    );
  };

  return (
    <Card interactive className="flex flex-col gap-3.5 p-4">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold tracking-wide text-muted ltr-field">#{panel.code}</span>
        {panel.enable ? (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-success/12 px-2.5 py-1 text-[11px] font-semibold text-success">
            <span className="h-1.5 w-1.5 rounded-full bg-success" />
            {t("panel.common.active")}
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-surface-2 px-2.5 py-1 text-[11px] font-semibold text-muted">
            <span className="h-1.5 w-1.5 rounded-full bg-muted" />
            {t("panel.common.inactive")}
          </span>
        )}
      </div>

      <div className="flex items-center gap-3">
        <div
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border text-lg font-bold text-primary"
          style={{ background: accent.bg, borderColor: accent.border }}
        >
          {panel.name.trim().charAt(0) || "؟"}
        </div>
        <div className="min-w-0">
          <div className="truncate font-bold text-text">{panel.name}</div>
          <div className="mt-0.5 flex items-center gap-1.5 truncate text-xs text-muted">
            <Globe size={12} className="shrink-0" />
            <span className="ltr-field truncate">{panel.base_url}</span>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <span className="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface-2 px-2.5 py-1 text-[11px] text-muted">
          {panel.auth_type === "api_key" ? <KeyRound size={11} /> : <Lock size={11} />}
          {panel.auth_type === "api_key" ? "API Key" : t("panel.panels.usernamePassword")}
        </span>
        {trialEnabled && (
          <span className="inline-flex items-center gap-1.5 rounded-md border border-[rgba(196,138,255,0.35)] bg-[rgba(196,138,255,0.13)] px-2.5 py-1 text-[11px] font-semibold text-[#C48AFF]">
            <Gift size={11} />
            {t("panel.panels.trialActiveBadge")}
          </span>
        )}
      </div>

      <div className="h-px bg-border/60" />

      <div className="flex items-center gap-1.5">
        <button className={iconButtonClass} title={t("panel.panels.viewInfo")} onClick={onView}>
          <Eye size={14} />
        </button>
        <button className={iconButtonClass} title={t("panel.panels.quickEdit")} onClick={onEdit}>
          <Pencil size={14} />
        </button>
        <button className={iconButtonClass} title={t("panel.panels.fullSettings")} onClick={onSettings}>
          <Settings size={14} />
        </button>

        {test.isPending ? (
          <div className="flex h-8 flex-1 items-center justify-center gap-2 rounded-md border border-border bg-surface-2 text-xs text-muted">
            <span className="h-3 w-3 animate-spin rounded-full border-2 border-muted/30 border-t-primary" />
            {t("panel.panels.testing")}
          </div>
        ) : pingMs !== null ? (
          <button
            className="flex h-8 flex-1 items-center justify-center gap-1.5 rounded-md border border-success/30 bg-success/12 text-xs font-bold text-success"
            onClick={handleTest}
          >
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-success" />
            {pingMs} ms
          </button>
        ) : (
          <button
            className={`${iconButtonClass} flex-1 gap-1.5`}
            onClick={handleTest}
            title={t("panel.panels.testConnection")}
          >
            <Activity size={13} />
            <span className="text-xs">{t("panel.panels.testConnection")}</span>
          </button>
        )}

        <ConfirmButton
          variant="ghost"
          className="!h-8 !w-8 !gap-0 !p-0 rounded-md text-muted hover:bg-danger/10 hover:text-danger"
          message={t("panel.panels.deleteConfirm")}
          onConfirm={() => remove.mutate({ code: panel.code })}
        >
          <Trash2 size={14} />
        </ConfirmButton>
      </div>
    </Card>
  );
}
