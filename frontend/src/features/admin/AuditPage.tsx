import { useState } from "react";
import { Filter, SlidersHorizontal } from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge, ErrorState, Modal, Pagination, Skeleton } from "../../components/ui";
import { formatNumber, formatUnixDate } from "../../lib/format";
import { panelAuditApi } from "../../api/panel";
import type { PanelAuditRow } from "../../types/panel";
import { usePanelQuery } from "../../queries/usePanelApi";
import { IconMenuButton, MenuHeader, MenuRow, SectionCard } from "./components";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

const actionLabels = (t: TFunction): Record<string, string> => ({
  balance_add: t("panel.common.addBalance"),
  balance_subtract: t("panel.audit.balanceDeduct"),
  user_block: t("panel.audit.userBlock"),
  user_unblock: t("panel.common.unblock"),
  user_message: t("panel.audit.messageSent"),
  user_phone_set: t("panel.audit.phoneSet"),
  user_phone_clear: t("panel.audit.phoneClear"),
  service_enable: t("panel.audit.serviceEnable"),
  service_disable: t("panel.audit.serviceDisable"),
  service_delete: t("panel.common.deleteService"),
  tx_approve: t("panel.audit.transactionApprove"),
  tx_reject: t("panel.audit.transactionReject"),
  panel_create: t("panel.common.addPanel"),
  panel_update: t("panel.audit.panelUpdate"),
  panel_delete: t("panel.audit.panelDelete"),
  plan_create: t("panel.common.addPlan"),
  plan_update: t("panel.audit.planUpdate"),
  plan_delete: t("panel.audit.planDelete"),
  reseller_update: t("panel.audit.resellerUpdate"),
  reseller_delete: t("panel.audit.resellerDelete"),
  reseller_plan_create: t("panel.common.addResellerPlan"),
  reseller_plan_update: t("panel.audit.resellerPlanUpdate"),
  reseller_plan_delete: t("panel.audit.resellerPlanDelete"),
  discount_create: t("panel.common.createDiscount"),
  discount_update: t("panel.audit.discountUpdate"),
  discount_delete: t("panel.audit.discountDelete"),
  broadcast_create: t("panel.audit.broadcastCreate"),
  broadcast_pause: t("panel.audit.broadcastPause"),
  broadcast_resume: t("panel.audit.broadcastResume"),
  broadcast_cancel: t("panel.audit.broadcastCancel"),
  channel_create: t("panel.common.addChannel"),
  channel_delete: t("panel.audit.channelDelete"),
  log_channel_set: t("panel.audit.reportTargetSet"),
  log_channel_delete: t("panel.audit.reportTargetDelete"),
  bot_text_update: t("panel.audit.textUpdate"),
  bot_text_delete: t("panel.audit.textDelete"),
  keyboard_layout_update: t("panel.audit.keyboardLayoutUpdate"),
  keyboard_layout_reset: t("panel.audit.keyboardLayoutReset"),
  keyboard_button_update: t("panel.audit.keyboardButtonUpdate"),
  keyboard_icon_clear: t("panel.audit.keyboardIconClear"),
  settings_update: t("panel.audit.settingsUpdate"),
  referral_settings_update: t("panel.audit.referralUpdate"),
  wallet_create: t("panel.common.addWallet"),
  wallet_delete: t("panel.audit.walletDelete"),
  card_create: t("panel.common.addCard"),
  card_activate: t("panel.audit.cardEnable"),
  card_delete: t("panel.audit.cardDelete"),
  auto_approve_rule_create: t("panel.audit.autoRuleAdd"),
  auto_approve_rule_update: t("panel.audit.autoRuleUpdate"),
  auto_approve_rule_delete: t("panel.audit.autoRuleDelete"),
  backup_send: t("panel.audit.backupToChannel"),
  backup_send_admin: t("panel.audit.backupToAdmin"),
  bulk_increase_start: t("panel.common.startBulkIncrease"),
  bulk_increase_done: t("panel.audit.bulkIncreaseDone"),
  bulk_increase_failed: t("panel.audit.bulkIncreaseError"),
});

const DESTRUCTIVE = /_(delete|reject|disable|failed)$/;

export default function AdminAuditPage() {
  const { t } = useTranslation();
  const [action, setAction] = useState("");
  const [page, setPage] = useState(1);
  const [detailRow, setDetailRow] = useState<PanelAuditRow | null>(null);

  const query = usePanelQuery(["audit", action, page], (auth) =>
    panelAuditApi.listAudit({ ...auth, action, page, limit: 10 })
  );

  const actionOptions = [
    { value: "", label: t("panel.audit.allActions"), icon: Filter },
    ...(query.data?.actions || []).map((value) => ({ value, label: actionLabels(t)[value] || value, icon: undefined })),
  ];

  const rows = query.data?.entries || [];

  function updateAction(value: string) {
    setAction(value);
    setPage(1);
  }

  return (
    <>
      <PageHeader
        title={t("panel.common.auditLog")}
        subtitle={query.data ? t("panel.audit.countLabel", { count: formatNumber(query.data.meta.total) }) : undefined}
      />

      <SectionCard title={t("panel.audit.subtitle")}>
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-surface p-2.5">
          <IconMenuButton
            icon={SlidersHorizontal}
            title={t("panel.audit.actionType")}
            active={action !== ""}
            badge={action !== ""}
            width={224}
            heightEstimate={320}
          >
            {(close) => (
              <>
                <MenuHeader title={t("panel.audit.actionType")} />
                {actionOptions.map((opt) => (
                  <MenuRow
                    key={opt.value}
                    icon={opt.icon}
                    label={opt.label}
                    active={opt.value === action}
                    onClick={() => {
                      updateAction(opt.value);
                      close();
                    }}
                  />
                ))}
              </>
            )}
          </IconMenuButton>
          {action !== "" && (
            <Badge tone="primary">{actionLabels(t)[action] || action}</Badge>
          )}
        </div>

        {query.isError ? (
          <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
        ) : query.isLoading ? (
          <div className="mt-4 space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-14 w-full rounded-md" />
            ))}
          </div>
        ) : rows.length ? (
          <div className="mt-2 divide-y divide-border/60">
            {rows.map((row) => (
              <button
                key={row.id}
                type="button"
                onClick={() => setDetailRow(row)}
                className="flex w-full flex-wrap items-center gap-2.5 py-2.5 text-start first:pt-0 last:pb-0 hover:bg-surface-2/60"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <Badge tone={DESTRUCTIVE.test(row.action) ? "danger" : "muted"}>
                      {actionLabels(t)[row.action] || row.action}
                    </Badge>
                  </div>
                  <div className="mt-1 text-[11px] text-muted">
                    <code className="ltr-field">{row.actor_username || row.actor_id || "—"}</code>
                    {row.target_type ? ` · ${[row.target_type, row.target_id].filter(Boolean).join(" ")}` : ""}
                  </div>
                </div>
                <div className="text-[11px] text-muted">{row.created_at ? formatUnixDate(row.created_at) : "—"}</div>
              </button>
            ))}
          </div>
        ) : (
          <p className="py-8 text-center text-sm text-muted">{t("panel.audit.empty")}</p>
        )}

        <div className="mt-4">
          <Pagination page={page} totalPages={query.data?.meta.total_pages || 1} onChange={setPage} />
        </div>
      </SectionCard>

      <Modal
        open={detailRow != null}
        onClose={() => setDetailRow(null)}
        title={detailRow ? t("panel.audit.detailTitle", { id: detailRow.id }) : ""}
      >
        {detailRow && (
          <div className="space-y-3 text-sm">
            <DetailRow label={t("panel.common.time")} value={detailRow.created_at ? formatUnixDate(detailRow.created_at) : "—"} />
            <DetailRow label={t("panel.audit.admin")} value={detailRow.actor_username || String(detailRow.actor_id ?? "—")} ltr />
            <DetailRow label={t("panel.common.actions")} value={actionLabels(t)[detailRow.action] || detailRow.action} />
            <DetailRow
              label={t("panel.audit.target")}
              value={[detailRow.target_type, detailRow.target_id].filter(Boolean).join(" ") || "—"}
            />
            <DetailRow label="IP" value={detailRow.ip || "—"} ltr />
            <div>
              <p className="mb-1 text-xs text-muted">{t("panel.common.details")}</p>
              {detailRow.detail && Object.keys(detailRow.detail).length ? (
                <pre className="ltr-field max-h-64 overflow-auto rounded-md bg-surface-2 p-3 text-xs leading-relaxed text-text">
                  {JSON.stringify(detailRow.detail, null, 2)}
                </pre>
              ) : (
                <p className="text-xs text-muted">{t("panel.audit.noDetail")}</p>
              )}
            </div>
          </div>
        )}
      </Modal>
    </>
  );
}

function DetailRow({ label, value, ltr = false }: { label: string; value: string; ltr?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-border/60 pb-2 text-xs">
      <span className="shrink-0 text-muted">{label}</span>
      <span className={`min-w-0 truncate font-medium text-text ${ltr ? "ltr-field" : ""}`}>{value}</span>
    </div>
  );
}
