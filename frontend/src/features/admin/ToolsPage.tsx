import { useState } from "react";
import { Cpu, HardDrive, MemoryStick, Timer } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Card, EmptyState, ErrorState, IconBadge, Input, ProgressRing, Skeleton } from "../../components/ui";
import { panelToolsApi } from "../../api/panel";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { ConfirmButton, SectionCard, SelectField, Toggle } from "./components";
import { useTranslation } from "react-i18next";
import { formatJobTime } from "../../lib/format";

const GB = 1024 ** 3;

function gigabytes(bytes: number): string {
  return `${(bytes / GB).toFixed(1)} GB`;
}

function ringTone(percent: number): "primary" | "warning" | "danger" {
  if (percent >= 90) return "danger";
  if (percent >= 70) return "warning";
  return "primary";
}

/** Job ids are internal snake_case identifiers (e.g. "check_low_volume") —
 * this is purely a display nicety, not a translation, so it stays client-side
 * rather than needing an i18n key per job. */
function humanizeJobId(id: string): string {
  return id.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function ResourceGauge({
  icon: Icon,
  label,
  percent,
  hint,
}: {
  icon: LucideIcon;
  label: string;
  percent: number;
  hint?: string;
}) {
  const value = Math.max(0, Math.min(100, percent || 0));
  return (
    <Card className="flex flex-col items-center gap-2 p-3 text-center sm:gap-3 sm:p-5">
      <div className="flex items-center gap-1.5 text-[11px] font-medium text-muted sm:text-xs">
        <Icon size={14} strokeWidth={2} />
        {label}
      </div>
      <ProgressRing percent={Math.round(value)} tone={ringTone(value)} size={84} strokeWidth={7} />
      {hint && <p className="text-[10px] leading-tight text-muted sm:text-xs">{hint}</p>}
    </Card>
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

      <div className="grid grid-cols-3 gap-2 sm:gap-3">
        <ResourceGauge
          icon={Cpu}
          label={t("panel.tools.cpu")}
          percent={metrics.cpu_percent}
          hint={t("panel.tools.cpuCores", { count: metrics.cpu_cores })}
        />
        <ResourceGauge
          icon={MemoryStick}
          label={t("panel.tools.memory")}
          percent={metrics.ram_percent}
          hint={t("panel.tools.ramUsage", { used: gigabytes(metrics.ram_used), total: gigabytes(metrics.ram_total) })}
        />
        <ResourceGauge
          icon={HardDrive}
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
          {jobs.length ? (
            <div className="divide-y divide-border/60">
              {jobs.map((job) => (
                <div key={job.id} className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2 py-2.5 first:pt-0 last:pb-0">
                  <div className="flex min-w-0 items-center gap-2.5">
                    <IconBadge icon={Timer} tone="muted" size="sm" />
                    <span className="truncate text-sm text-text">{humanizeJobId(job.id)}</span>
                  </div>
                  <div className="flex shrink-0 items-center gap-4 text-[11px]">
                    <div className="text-end">
                      <p className="text-muted">{t("panel.tools.lastRun")}</p>
                      <p className="ltr-field text-text">{formatJobTime(job.last_run)}</p>
                    </div>
                    <div className="text-end">
                      <p className="text-muted">{t("panel.tools.nextRun")}</p>
                      <p className="ltr-field text-text">{formatJobTime(job.next_run)}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState icon={Timer} title={t("panel.tools.noSchedule")} />
          )}
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
