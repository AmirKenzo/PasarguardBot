import { useState } from "react";
import { PageHeader } from "../../components/layout/PageHeader";
import { ErrorState, Input, Skeleton } from "../../components/ui";
import { panelToolsApi } from "../../api/panel";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { ConfirmButton, DataTable, SectionCard, SelectField, Toggle } from "./components";
import type { Column } from "./components";
import { useTranslation } from "react-i18next";

const GB = 1024 ** 3;

function gigabytes(bytes: number): string {
  return `${(bytes / GB).toFixed(1)} GB`;
}

function Meter({ label, percent, hint }: { label: string; percent: number; hint?: string }) {
  const { t } = useTranslation();
  const value = Math.max(0, Math.min(100, percent || 0));
  const tone = value >= 90 ? "bg-danger" : value >= 70 ? "bg-warning" : "bg-success";
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted">{label}</span>
        <span className="font-medium text-text">{value.toFixed(1)}{t("panel.tools.percent")}</span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface-2">
        <div className={`h-full rounded-full ${tone}`} style={{ width: `${value}%` }} />
      </div>
      {hint && <p className="mt-1.5 text-xs text-muted">{hint}</p>}
    </div>
  );
}

export default function AdminToolsPage() {
  const { t } = useTranslation();
  const [bulk, setBulk] = useState({ panel: "all", volume: "", days: "", confirm: false });

  const query = usePanelQuery(["tools"], (auth) => panelToolsApi.getTools(auth), { refetchInterval: 30_000 });
  const backupToChannel = usePanelAction(panelToolsApi.backupToLogChannel);
  const backupToMe = usePanelAction(panelToolsApi.backupToMe);
  const bulkIncrease = usePanelAction(panelToolsApi.bulkIncrease, { invalidate: [["audit"]] });

  if (query.isError) {
    return <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />;
  }
  if (query.isLoading || !query.data) {
    return <Skeleton className="h-64 w-full" />;
  }

  const { metrics, versions, jobs, panels, backup_supported: backupSupported } = query.data;

  const jobColumns: Column<{ id: string; next_run?: string | null }>[] = [
    { key: "id", header: t("panel.tools.job"), cell: (row) => <code className="ltr-field text-xs">{row.id}</code> },
    { key: "next", header: t("panel.tools.nextRun"), cell: (row) => <span className="ltr-field text-xs">{row.next_run || "—"}</span> },
  ];

  const panelOptions = [
    { value: "all", label: t("panel.common.allPanels") },
    ...panels.map((panel) => ({ value: String(panel.code), label: panel.name })),
  ];

  const versionRows = [
    [t("panel.tools.botVersion"), versions.app],
    ["Telethon", versions.telethon ? `${versions.telethon} (layer ${versions.telethon_layer})` : null],
    ["FastAPI", versions.fastapi],
    [t("panel.tools.panelLibrary"), versions.pasarguard],
    [t("panel.tools.python"), metrics.python],
    [t("panel.tools.os"), metrics.platform],
    [t("panel.tools.database"), versions.database],
  ];

  return (
    <>
      <PageHeader title={t("panel.common.tools")} subtitle={t("panel.tools.subtitle")} />

      <div className="grid gap-3 sm:grid-cols-3">
        <Meter label={t("panel.tools.cpu")} percent={metrics.cpu_percent} hint={t("panel.tools.cpuCores", { count: metrics.cpu_cores })} />
        <Meter
          label={t("panel.tools.memory")}
          percent={metrics.ram_percent}
          hint={t("panel.tools.ramUsage", { used: gigabytes(metrics.ram_used), total: gigabytes(metrics.ram_total) })}
        />
        <Meter
          label={t("panel.tools.disk")}
          percent={metrics.disk_percent}
          hint={t("panel.tools.diskUsage", { used: gigabytes(metrics.disk_used), total: gigabytes(metrics.disk_total) })}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <SectionCard title={t("panel.tools.versions")}>
          <dl className="space-y-2 text-sm">
            {versionRows.map(([label, value]) => (
              <div key={label} className="flex items-center justify-between gap-3">
                <dt className="text-muted">{label}</dt>
                <dd className="ltr-field truncate text-xs text-text">{value || "—"}</dd>
              </div>
            ))}
          </dl>
        </SectionCard>

        <SectionCard title={t("panel.tools.schedulers", { count: jobs.length })}>
          <DataTable
            columns={jobColumns}
            rows={jobs}
            rowKey={(row) => row.id}
            emptyTitle={t("panel.tools.noSchedule")}
          />
        </SectionCard>
      </div>

      <SectionCard
        title={t("panel.tools.backupTitle")}
        description={
          backupSupported
            ? t("panel.tools.backupSecurity")
            : t("panel.tools.backupRequirements")
        }
      >
        <div className="flex flex-wrap gap-2">
          <ConfirmButton
            size="sm"
            disabled={!backupSupported}
            loading={backupToChannel.isPending}
            message={t("panel.tools.backupToChannelConfirm")}
            onConfirm={() => backupToChannel.mutate({})}
          >
            {t("panel.tools.sendToLogChannel")}
          </ConfirmButton>
          <ConfirmButton
            size="sm"
            variant="secondary"
            disabled={!backupSupported}
            loading={backupToMe.isPending}
            message={t("panel.tools.backupToMeConfirm")}
            onConfirm={() => backupToMe.mutate({})}
          >
            {t("panel.tools.sendToMe")}
          </ConfirmButton>
        </div>
      </SectionCard>

      <SectionCard
        title={t("panel.tools.bulkTitle")}
        description={t("panel.tools.bulkScope")}
      >
        <div className="grid gap-3 sm:grid-cols-3">
          <SelectField
            label={t("panel.common.panel")}
            options={panelOptions}
            value={bulk.panel}
            onChange={(event) => setBulk({ ...bulk, panel: event.target.value })}
          />
          <Input
            label={t("panel.tools.extraVolume")}
            inputMode="decimal"
            placeholder={t("panel.tools.egTen")}
            value={bulk.volume}
            onChange={(event) => setBulk({ ...bulk, volume: event.target.value })}
          />
          <Input
            label={t("panel.tools.extraDays")}
            inputMode="numeric"
            placeholder={t("panel.common.egThirty")}
            value={bulk.days}
            onChange={(event) => setBulk({ ...bulk, days: event.target.value })}
          />
        </div>
        <div className="mt-3">
          <Toggle
            checked={bulk.confirm}
            onChange={(confirm) => setBulk({ ...bulk, confirm })}
            label={t("panel.tools.bulkAcknowledge")}
          />
        </div>
        <div className="mt-3 flex justify-end">
          <ConfirmButton
            size="sm"
            variant="danger"
            disabled={!bulk.confirm || (!bulk.volume.trim() && !bulk.days.trim())}
            loading={bulkIncrease.isPending}
            message={t("panel.tools.bulkConfirm")}
            confirmLabel={t("panel.tools.start")}
            onConfirm={() =>
              bulkIncrease.mutate(
                {
                  panel: bulk.panel,
                  volume_gb: bulk.volume.trim() ? Number(bulk.volume) : null,
                  days: bulk.days.trim() ? Number(bulk.days) : null,
                  confirm: true,
                },
                { onSuccess: () => setBulk({ panel: "all", volume: "", days: "", confirm: false }) }
              )
            }
          >
            {t("panel.common.startBulkIncrease")}
          </ConfirmButton>
        </div>
        <p className="mt-2 text-xs text-muted">
          {t("panel.tools.runsInBackground")}
        </p>
      </SectionCard>
    </>
  );
}
