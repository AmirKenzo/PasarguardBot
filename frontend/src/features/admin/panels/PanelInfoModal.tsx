import type { ReactNode } from "react";
import { Download, Pause, Signal, Upload, UserCheck, UserX, Users, CalendarClock } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Modal, ProgressRing, Skeleton } from "../../../components/ui";
import { StatTile } from "../components";
import { panelPanelsApi } from "../../../api/panel";
import { usePanelQuery } from "../../../queries/usePanelApi";

function bytesToGb(value: number | null | undefined): string {
  if (value == null) return "—";
  return (value / 1024 ** 3).toLocaleString(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 });
}

function formatCount(value: number | null | undefined): string {
  if (value == null) return "—";
  return value.toLocaleString();
}

export interface PanelInfoModalProps {
  code: number | null;
  name?: string;
  onClose: () => void;
}

export function PanelInfoModal({ code, name, onClose }: PanelInfoModalProps) {
  const { t } = useTranslation();
  const query = usePanelQuery(["panel-status", code], (auth) => panelPanelsApi.getPanelStatus({ code: code as number, ...auth }), {
    enabled: code !== null,
  });

  const status = query.data;
  const ramPercent =
    status?.mem_total && status?.mem_used != null ? Math.round((status.mem_used / status.mem_total) * 100) : 0;

  return (
    <Modal open={code !== null} onClose={onClose} title={name || t("panel.panels.viewInfo")} size="lg">
      {query.isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : status ? (
        <div className="max-h-[72vh] space-y-5 overflow-y-auto pe-1">
          <div>
            <p className="mb-2 text-xs font-bold text-primary">{t("panel.panels.infoSpecTitle")}</p>
            <div className="divide-y divide-border/60 rounded-md border border-border bg-surface-2/40 px-3">
              <Row label={t("panel.common.status")}>
                {status.enable ? (
                  <span className="font-bold text-success">{t("panel.common.active")}</span>
                ) : (
                  <span className="font-bold text-danger">{t("panel.common.inactive")}</span>
                )}
              </Row>
              <Row label={t("panel.panels.shopSaleStatus")}>
                {status.shop_enabled ? (
                  <span className="font-bold text-success">{t("panel.common.active")}</span>
                ) : (
                  <span className="font-bold text-danger">{t("panel.common.inactive")}</span>
                )}
              </Row>
              <Row label={t("panel.panels.resellerSaleStatus")}>
                {status.reseller_enabled ? (
                  <span className="font-bold text-success">{t("panel.common.active")}</span>
                ) : (
                  <span className="font-bold text-danger">{t("panel.common.inactive")}</span>
                )}
              </Row>
              <Row label={t("panel.panels.authType")}>{status.auth_type === "api_key" ? "API Key" : t("panel.panels.usernamePassword")}</Row>
              <Row label={t("panel.panels.url")}>
                <span className="ltr-field">{status.base_url}</span>
              </Row>
              <Row label={t("panel.panels.tunnelUrl")}>
                <span className="ltr-field">{status.tunnel_url || t("panel.panels.tunnelNotSet")}</span>
              </Row>
            </div>
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between">
              <p className="text-xs font-bold text-primary">{t("panel.panels.infoServerTitle")}</p>
              {status.version && <span className="text-[11px] text-muted">{t("panel.panels.version")} {status.version}</span>}
            </div>

            {status.status_error ? (
              <div className="rounded-md border border-danger/30 bg-danger/10 p-3 text-xs text-danger">
                {status.status_error}
              </div>
            ) : (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <div className="flex flex-col items-center gap-1.5 rounded-md border border-border bg-surface-2/40 p-3">
                    <ProgressRing percent={ramPercent} size={84} strokeWidth={8} label={t("panel.panels.ram")} />
                    <span className="text-[11px] text-muted">
                      {bytesToGb(status.mem_used)} / {bytesToGb(status.mem_total)} GB
                    </span>
                  </div>
                  <div className="flex flex-col items-center gap-1.5 rounded-md border border-border bg-surface-2/40 p-3">
                    <ProgressRing
                      percent={Math.round(status.cpu_usage || 0)}
                      size={84}
                      strokeWidth={8}
                      tone="warning"
                      label={t("panel.panels.cpu")}
                    />
                    <span className="text-[11px] text-muted">
                      {status.cpu_cores ?? "—"} {t("panel.panels.cores")}
                    </span>
                  </div>
                </div>

                <div className="mt-3 grid grid-cols-2 gap-2.5 sm:grid-cols-3">
                  <StatTile icon={Users} label={t("panel.panels.usersTotal")} value={formatCount(status.total_user)} />
                  <StatTile icon={Signal} tone="success" label={t("panel.panels.usersOnline")} value={formatCount(status.online_users)} />
                  <StatTile icon={UserCheck} tone="success" label={t("panel.panels.usersActive")} value={formatCount(status.active_users)} />
                  <StatTile icon={Pause} label={t("panel.panels.usersOnHold")} value={formatCount(status.on_hold_users)} />
                  <StatTile icon={UserX} tone="danger" label={t("panel.panels.usersDisabled")} value={formatCount(status.disabled_users)} />
                  <StatTile icon={CalendarClock} tone="warning" label={t("panel.panels.usersExpired")} value={formatCount(status.expired_users)} />
                </div>

                <div className="mt-2.5 grid grid-cols-2 gap-2.5">
                  <StatTile icon={Download} label={t("panel.panels.download")} value={`${bytesToGb(status.incoming_bandwidth)} GB`} />
                  <StatTile icon={Upload} label={t("panel.panels.upload")} value={`${bytesToGb(status.outgoing_bandwidth)} GB`} />
                </div>
              </>
            )}
          </div>
        </div>
      ) : null}
    </Modal>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2.5 text-xs">
      <span className="text-muted">{label}</span>
      <span className="min-w-0 truncate text-text">{children}</span>
    </div>
  );
}
