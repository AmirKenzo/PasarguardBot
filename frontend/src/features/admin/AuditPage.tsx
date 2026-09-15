import { useState } from "react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge, Button, ErrorState, Pagination } from "../../components/ui";
import { formatNumber, formatUnixDate } from "../../lib/format";
import { panelAuditApi } from "../../api/panel";
import type { PanelAuditRow } from "../../types/panel";
import { usePanelQuery } from "../../queries/usePanelApi";
import { DataTable, SectionCard, SelectField, Toolbar } from "./components";
import type { Column } from "./components";
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
  const [draftAction, setDraftAction] = useState("");
  const [page, setPage] = useState(1);

  const query = usePanelQuery(["audit", action, page], (auth) =>
    panelAuditApi.listAudit({ ...auth, action, page, limit: 50 })
  );

  const actionOptions = [
    { value: "", label: t("panel.audit.allActions") },
    ...(query.data?.actions || []).map((value) => ({ value, label: actionLabels(t)[value] || value })),
  ];

  const columns: Column<PanelAuditRow>[] = [
    {
      key: "time",
      header: t("panel.common.time"),
      cell: (row) => (
        <span className="text-xs text-muted">{row.created_at ? formatUnixDate(row.created_at) : "—"}</span>
      ),
    },
    {
      key: "admin",
      header: t("panel.audit.admin"),
      cell: (row) => <code className="ltr-field text-xs">{row.admin_username || row.admin_id || "—"}</code>,
    },
    {
      key: "action",
      header: t("panel.common.actions"),
      cell: (row) => (
        <Badge tone={DESTRUCTIVE.test(row.action) ? "danger" : "muted"}>
          {actionLabels(t)[row.action] || row.action}
        </Badge>
      ),
    },
    {
      key: "target",
      header: t("panel.audit.target"),
      secondary: true,
      cell: (row) => (
        <span className="text-xs">{[row.target_type, row.target_id].filter(Boolean).join(" ") || "—"}</span>
      ),
    },
    {
      key: "detail",
      header: t("panel.common.details"),
      secondary: true,
      cell: (row) => (
        <span className="block max-w-[18rem] truncate text-xs text-muted" title={JSON.stringify(row.detail ?? {})}>
          {row.detail
            ? Object.entries(row.detail)
                .map(([key, value]) => `${key}: ${String(value)}`)
                .join(t("panel.common.listSeparator"))
            : "—"}
        </span>
      ),
    },
    {
      key: "ip",
      header: "IP",
      secondary: true,
      cell: (row) => <code className="ltr-field text-xs text-muted">{row.ip || "—"}</code>,
    },
  ];

  return (
    <>
      <PageHeader
        title={t("panel.common.auditLog")}
        subtitle={query.data ? t("panel.audit.countLabel", { count: formatNumber(query.data.meta.total) }) : undefined}
      />

      <Toolbar
        onSubmit={() => {
          setPage(1);
          setAction(draftAction);
        }}
      >
        <div className="min-w-[14rem] flex-1">
          <SelectField
            label={t("panel.audit.actionType")}
            options={actionOptions}
            value={draftAction}
            onChange={(event) => setDraftAction(event.target.value)}
          />
        </div>
        <Button size="md" type="submit" variant="secondary">
          {t("panel.common.applyFilter")}
        </Button>
      </Toolbar>

      {query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : (
        <SectionCard title={t("panel.audit.subtitle")}>
          <DataTable
            columns={columns}
            rows={query.data?.entries || []}
            rowKey={(row) => row.id}
            loading={query.isLoading}
            emptyTitle={t("panel.audit.empty")}
          />
          <div className="mt-4">
            <Pagination page={page} totalPages={query.data?.meta.total_pages || 1} onChange={setPage} />
          </div>
        </SectionCard>
      )}
    </>
  );
}
