import { useState } from "react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge, Button, ErrorState, Input } from "../../components/ui";
import { formatNumber, formatUnixDate } from "../../lib/format";
import { panelBroadcastApi } from "../../api/panel";
import type { PanelBroadcastJobRow } from "../../types/panel";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { ConfirmButton, DataTable, SectionCard, SelectField } from "./components";
import type { Column } from "./components";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

const targetLabels = (t: TFunction): Record<string, string> => ({
  all: t("panel.broadcast.allUsers"),
  active: t("panel.broadcast.activeUsers"),
  users_with_active_service: t("panel.broadcast.usersWithActiveService"),
});

const statusLabels = (t: TFunction): Record<string, string> => ({
  draft: t("panel.broadcast.draft"),
  pending_confirm: t("panel.common.awaitingApproval"),
  queued: t("panel.broadcast.queued"),
  running: t("panel.broadcast.sending"),
  paused: t("panel.broadcast.paused"),
  canceled: t("panel.broadcast.cancelled"),
  done: t("panel.broadcast.finished"),
  failed: t("panel.broadcast.failed"),
});

const STATUS_TONE: Record<string, "success" | "warning" | "danger" | "primary" | "muted"> = {
  running: "primary",
  queued: "warning",
  paused: "warning",
  done: "success",
  failed: "danger",
};

export default function AdminBroadcastPage() {
  const { t } = useTranslation();
  const [form, setForm] = useState({
    text: "",
    target_mode: "all",
    delay_ms: "300",
    batch_size: "50",
    batch_delay_ms: "2000",
  });

  const query = usePanelQuery(["broadcast"], (auth) => panelBroadcastApi.getBroadcast(auth), {
    refetchInterval: 10_000,
  });

  const invalidate = [["broadcast"]];
  const send = usePanelAction(panelBroadcastApi.send, { invalidate });
  const pause = usePanelAction(panelBroadcastApi.pause, { invalidate });
  const resume = usePanelAction(panelBroadcastApi.resume, { invalidate });
  const cancel = usePanelAction(panelBroadcastApi.cancel, { invalidate });

  const targetOptions = (query.data?.target_modes || ["all"]).map((value) => ({
    value,
    label: targetLabels(t)[value] || value,
  }));

  const columns: Column<PanelBroadcastJobRow>[] = [
    { key: "id", header: "#", cell: (row) => <code className="ltr-field text-xs">{row.id}</code> },
    {
      key: "text",
      header: t("panel.common.text"),
      cell: (row) => (
        <span className="block max-w-[16rem] truncate text-xs" title={row.text}>
          {row.text || "—"}
        </span>
      ),
    },
    {
      key: "target",
      header: t("panel.broadcast.audience"),
      secondary: true,
      cell: (row) => targetLabels(t)[row.target_mode] || row.target_mode,
    },
    {
      key: "progress",
      header: t("panel.broadcast.progress"),
      cell: (row) => `${formatNumber(row.sent_ok)} / ${formatNumber(row.total_targets)}`,
    },
    { key: "failed", header: t("panel.broadcast.failed"), secondary: true, cell: (row) => formatNumber(row.sent_fail) },
    {
      key: "status",
      header: t("panel.common.status"),
      cell: (row) => (
        <Badge tone={STATUS_TONE[row.status || ""] || "muted"}>{statusLabels(t)[row.status || ""] || row.status}</Badge>
      ),
    },
    {
      key: "created",
      header: t("panel.broadcast.create"),
      secondary: true,
      cell: (row) => (
        <span className="text-xs text-muted">{row.created_at ? formatUnixDate(row.created_at) : "—"}</span>
      ),
    },
    {
      key: "actions",
      header: t("panel.common.actions"),
      cell: (row) => (
        <div className="flex flex-wrap gap-1.5">
          {row.can_pause && (
            <Button size="sm" variant="ghost" onClick={() => pause.mutate({ job_id: row.id })}>
              {t("panel.broadcast.pause")}
            </Button>
          )}
          {row.can_resume && (
            <Button size="sm" variant="ghost" onClick={() => resume.mutate({ job_id: row.id })}>
              {t("panel.broadcast.resume")}
            </Button>
          )}
          {row.can_cancel && (
            <ConfirmButton
              size="sm"
              variant="danger"
              message={t("panel.broadcast.cancelConfirm")}
              onConfirm={() => cancel.mutate({ job_id: row.id })}
            >
              {t("common.cancel")}
            </ConfirmButton>
          )}
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader title={t("panel.common.broadcast")} subtitle={t("panel.broadcast.subtitle")} />

      <SectionCard title={t("panel.broadcast.newMessage")}>
        <div className="space-y-3">
          <label className="block text-sm">
            <span className="mb-1.5 block text-muted">{t("panel.broadcast.messageText")}</span>
            <textarea
              rows={6}
              maxLength={4000}
              value={form.text}
              onChange={(event) => setForm({ ...form, text: event.target.value })}
              className="w-full rounded-md border border-border bg-surface p-3 text-text outline-none focus:border-primary focus:ring-4 focus:ring-primary/10"
            />
            <span className="mt-1 block text-xs text-muted">{form.text.length} / 4000</span>
          </label>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <SelectField
              label={t("panel.broadcast.audiences")}
              options={targetOptions}
              value={form.target_mode}
              onChange={(event) => setForm({ ...form, target_mode: event.target.value })}
            />
            <Input
              label={t("panel.broadcast.sendDelay")}
              inputMode="numeric"
              value={form.delay_ms}
              onChange={(event) => setForm({ ...form, delay_ms: event.target.value })}
            />
            <Input
              label={t("panel.broadcast.batchSize")}
              inputMode="numeric"
              value={form.batch_size}
              onChange={(event) => setForm({ ...form, batch_size: event.target.value })}
            />
            <Input
              label={t("panel.broadcast.batchDelay")}
              inputMode="numeric"
              value={form.batch_delay_ms}
              onChange={(event) => setForm({ ...form, batch_delay_ms: event.target.value })}
            />
          </div>
          <p className="text-xs text-muted">
            {t("panel.broadcast.delayHint")}
          </p>
          <div className="flex justify-end">
            <ConfirmButton
              size="sm"
              disabled={!form.text.trim()}
              loading={send.isPending}
              message={t("panel.broadcast.startConfirm", { audience: targetLabels(t)[form.target_mode] || form.target_mode })}
              confirmLabel={t("panel.broadcast.start")}
              onConfirm={() =>
                send.mutate(
                  {
                    text: form.text.trim(),
                    target_mode: form.target_mode,
                    delay_ms: Number(form.delay_ms) || 0,
                    batch_size: Number(form.batch_size) || 50,
                    batch_delay_ms: Number(form.batch_delay_ms) || 0,
                  },
                  { onSuccess: () => setForm({ ...form, text: "" }) }
                )
              }
            >
              {t("panel.broadcast.saveAndStart")}
            </ConfirmButton>
          </div>
        </div>
      </SectionCard>

      {query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : (
        <SectionCard title={t("panel.broadcast.runningJobs")} description={t("panel.broadcast.refreshNote")}>
          <DataTable
            columns={columns}
            rows={query.data?.jobs || []}
            rowKey={(row) => row.id}
            loading={query.isLoading}
            emptyTitle={t("panel.broadcast.noJobs")}
          />
        </SectionCard>
      )}
    </>
  );
}
