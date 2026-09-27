import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Spinner } from "../../components/ui";
import { panelPanelsApi, panelUsersApi } from "../../api/panel";
import type { PanelTransferResult, PanelTransferResultRow, PanelTransferStatusResponse } from "../../types/panel";
import { formatBytes, formatNumber } from "../../lib/format";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { FormModal, SelectField, Toggle } from "./components";

const RESULT_TONE: Record<PanelTransferResult, "success" | "warning" | "danger" | "primary" | "muted"> = {
  moved: "success",
  moved_linked: "primary",
  moved_no_record: "warning",
  failed: "danger",
  conflict: "muted",
  unlimited: "muted",
};

const STATUS_ORDER = ["active", "on_hold", "limited", "expired", "disabled"];

/** Moves a panel admin's active users onto another admin of the same panel and
 *  records each moved user as a bot service of this Telegram id. The source
 *  admin itself is left untouched. */
export function UserTransferDialog({
  open,
  onClose,
  userId,
  invalidate,
}: {
  open: boolean;
  onClose: () => void;
  userId: number;
  invalidate: (string | number)[][];
}) {
  const { t } = useTranslation();
  const [panelCode, setPanelCode] = useState("");
  const [source, setSource] = useState("");
  const [previewOn, setPreviewOn] = useState(false);
  const [notify, setNotify] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);

  const code = Number(panelCode);
  const panels = usePanelQuery(["panels"], (auth) => panelPanelsApi.listPanels(auth), { enabled: open });
  const admins = usePanelQuery(
    ["user-transfer-admins", userId, code],
    (auth) => panelUsersApi.transferAdmins({ ...auth, user_id: userId, panel_code: code }),
    { enabled: open && code > 0 && !jobId, retry: false, staleTime: 30_000 }
  );
  const preview = usePanelQuery(
    ["user-transfer-preview", userId, code, source],
    (auth) => panelUsersApi.transferPreview({ ...auth, user_id: userId, panel_code: code, source_admin: source }),
    { enabled: open && previewOn && code > 0 && Boolean(source) && !jobId, retry: false, staleTime: 0 }
  );
  const status = usePanelQuery(
    ["user-transfer-status", jobId || ""],
    (auth) => panelUsersApi.transferStatus({ ...auth, job_id: jobId as string }),
    {
      enabled: Boolean(jobId),
      retry: false,
      refetchInterval: (q) => (q.state.data && q.state.data.state !== "running" ? false : 1500),
    }
  );
  const start = usePanelAction(panelUsersApi.transferStart);
  const queryClient = useQueryClient();
  const finished = Boolean(status.data && status.data.state !== "running");

  // Preselect the admin whose note or Telegram id matches this user.
  useEffect(() => {
    if (!admins.data) return;
    const suggested = admins.data.admins.find((admin) => admin.suggested);
    setSource((current) => current || suggested?.username || "");
  }, [admins.data]);

  // The user's service list only changes once the background job has finished.
  useEffect(() => {
    if (!finished) return;
    for (const key of invalidate) {
      void queryClient.invalidateQueries({ queryKey: ["panel", ...key] });
    }
  }, [finished, invalidate, queryClient]);

  function resetSelection(nextPanel: string) {
    setPanelCode(nextPanel);
    setSource("");
    setPreviewOn(false);
    setConfirming(false);
  }

  function resetAll() {
    resetSelection("");
    setJobId(null);
    setNotify(false);
  }

  const panelOptions = [
    { value: "", label: t("panel.userDetail.transfer.choosePanel") },
    ...(panels.data?.panels || []).map((panel) => ({ value: String(panel.code), label: `${panel.name} (#${panel.code})` })),
  ];
  const botAdmin = admins.data?.current_admin || "";
  const adminOptions = [
    { value: "", label: t("panel.userDetail.transfer.chooseAdmin") },
    ...(admins.data?.admins || []).map((admin) => ({
      value: admin.username,
      label: `${admin.suggested ? "★ " : ""}${admin.username} — ${t("panel.userDetail.transfer.usersCount", {
        count: formatNumber(admin.total_users),
      })}${admin.status && admin.status !== "active" ? ` (${admin.status})` : ""}`,
    })),
  ];

  const p = preview.data;
  const toMove = p ? p.will_create + p.already_linked : 0;

  return (
    <FormModal open={open} onClose={onClose} title={t("panel.userDetail.transfer.title", { id: userId })} size="xl">
      {jobId ? (
        <TransferProgress status={status.data} loading={status.isLoading} error={status.error?.message} onReset={resetAll} />
      ) : (
        <div className="space-y-4">
          <p className="text-xs text-muted">{t("panel.userDetail.transfer.intro")}</p>
          <p className="rounded-md bg-warning/10 p-2 text-[11px] text-warning">{t("panel.userDetail.transfer.unlimitedNotice")}</p>

          <SelectField
            label={t("panel.userDetail.transfer.panel")}
            value={panelCode}
            options={panelOptions}
            onChange={(event) => resetSelection(event.target.value)}
          />

          {code > 0 && admins.isLoading && (
            <div className="flex items-center gap-2 text-xs text-muted">
              <Spinner size={14} /> {t("panel.userDetail.transfer.checkingAccess")}
            </div>
          )}
          {code > 0 && admins.isError && (
            <p className="rounded-md bg-danger/10 p-3 text-xs text-danger">{admins.error?.message}</p>
          )}

          {admins.data && (
            <>
              <p className="text-[11px] text-muted">{t("panel.userDetail.transfer.targetHint", { admin: botAdmin || "—" })}</p>
              <SelectField
                label={t("panel.userDetail.transfer.sourceAdmin")}
                value={source}
                options={adminOptions}
                hint={t("panel.userDetail.transfer.sourceHint")}
                onChange={(event) => {
                  setSource(event.target.value);
                  setPreviewOn(false);
                  setConfirming(false);
                }}
              />
            </>
          )}

          {admins.data && !previewOn && (
            <div className="flex justify-end">
              <Button size="sm" disabled={!source} onClick={() => setPreviewOn(true)}>
                {t("panel.userDetail.transfer.preview")}
              </Button>
            </div>
          )}

          {previewOn && preview.isLoading && (
            <div className="flex items-center gap-2 text-xs text-muted">
              <Spinner size={14} /> {t("panel.userDetail.transfer.loadingUsers")}
            </div>
          )}
          {previewOn && preview.isError && (
            <p className="rounded-md bg-danger/10 p-3 text-xs text-danger">{preview.error?.message}</p>
          )}

          {previewOn && p && (
            <div className="space-y-3 rounded-lg border border-border p-3">
              <div className="flex flex-wrap gap-1.5">
                <Badge tone="muted">{t("panel.userDetail.transfer.totalUsers", { count: formatNumber(p.total_users) })}</Badge>
                {STATUS_ORDER.filter((key) => p.status_counts[key]).map((key) => (
                  <Badge key={key} tone={key === "active" ? "success" : "muted"}>
                    {key}: {formatNumber(p.status_counts[key] ?? 0)}
                  </Badge>
                ))}
              </div>
              <dl className="divide-y divide-border/60 text-xs">
                <Row label={t("panel.userDetail.transfer.willMove")} value={formatNumber(toMove)} strong />
                <Row label={t("panel.userDetail.transfer.willCreate")} value={formatNumber(p.will_create)} />
                <Row label={t("panel.userDetail.transfer.alreadyLinked")} value={formatNumber(p.already_linked)} />
                <Row label={t("panel.userDetail.transfer.skippedInactive")} value={formatNumber(p.total_users - p.active_users)} />
                <Row label={t("panel.userDetail.transfer.unlimitedSkipped")} value={formatNumber(p.unlimited_total)} />
                <Row label={t("panel.userDetail.transfer.conflicts")} value={formatNumber(p.conflicts_total)} />
                <Row
                  label={t("panel.userDetail.transfer.traffic")}
                  value={`${formatBytes(p.active_used_traffic, 1)} / ${formatBytes(p.active_data_limit, 1)}`}
                />
              </dl>
              {p.unlimited.length > 0 && (
                <div className="rounded-md bg-surface-2 p-2 text-[11px] text-muted">
                  <div className="mb-1 font-semibold text-text">{t("panel.userDetail.transfer.unlimitedHint")}</div>
                  <div className="ltr-field max-h-24 overflow-y-auto">
                    {p.unlimited.map((u) => `${u.username} (${u.reason})`).join(" · ")}
                  </div>
                </div>
              )}
              {p.conflicts.length > 0 && (
                <div className="rounded-md bg-warning/10 p-2 text-[11px] text-warning">
                  <div className="mb-1 font-semibold">{t("panel.userDetail.transfer.conflictsHint")}</div>
                  <div className="ltr-field max-h-24 overflow-y-auto">
                    {p.conflicts.map((c) => `${c.username} → ${c.owner_id}`).join(" · ")}
                  </div>
                </div>
              )}
              <Toggle checked={notify} onChange={setNotify} label={t("panel.userDetail.notifyUser")} />
              <div className="flex flex-wrap items-center justify-end gap-2">
                {confirming ? (
                  <>
                    <span className="text-xs text-warning">
                      {t("panel.userDetail.transfer.confirmText", {
                        count: formatNumber(toMove),
                        source,
                        target: p.target_admin || botAdmin,
                      })}
                    </span>
                    <Button size="sm" variant="ghost" onClick={() => setConfirming(false)}>
                      {t("panel.common.dismiss")}
                    </Button>
                    <Button
                      size="sm"
                      loading={start.isPending}
                      onClick={() =>
                        start.mutate(
                          { user_id: userId, panel_code: code, source_admin: source, notify },
                          { onSuccess: (res) => res.job_id && setJobId(res.job_id) }
                        )
                      }
                    >
                      {t("panel.common.confirm")}
                    </Button>
                  </>
                ) : (
                  <>
                    <Button size="sm" variant="ghost" onClick={() => void preview.refetch()}>
                      {t("panel.userDetail.transfer.refresh")}
                    </Button>
                    <Button size="sm" disabled={toMove === 0} onClick={() => setConfirming(true)}>
                      {t("panel.userDetail.transfer.start")}
                    </Button>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </FormModal>
  );
}

function TransferProgress({
  status,
  loading,
  error,
  onReset,
}: {
  status?: PanelTransferStatusResponse;
  loading: boolean;
  error?: string;
  onReset: () => void;
}) {
  const { t } = useTranslation();
  const [filter, setFilter] = useState<PanelTransferResult | "">("");

  const rows = useMemo(
    () => (status?.rows || []).filter((row) => (filter ? row.result === filter : row.result !== "moved")),
    [status?.rows, filter]
  );

  if (loading || !status) {
    return (
      <div className="flex items-center gap-2 py-6 text-sm text-muted">
        <Spinner size={16} /> {error || t("panel.userDetail.transfer.starting")}
      </div>
    );
  }

  const running = status.state === "running";
  const percent = status.total ? Math.round((status.processed / status.total) * 100) : running ? 0 : 100;
  const counts = status.counts;
  const moved = (counts.moved || 0) + (counts.moved_linked || 0) + (counts.moved_no_record || 0);
  const resultLabels: Record<PanelTransferResult, string> = {
    moved: t("panel.userDetail.transfer.result.moved"),
    moved_linked: t("panel.userDetail.transfer.result.moved_linked"),
    moved_no_record: t("panel.userDetail.transfer.result.moved_no_record"),
    failed: t("panel.userDetail.transfer.result.failed"),
    conflict: t("panel.userDetail.transfer.result.conflict"),
    unlimited: t("panel.userDetail.transfer.result.unlimited"),
  };

  return (
    <div className="space-y-4">
      <div className="text-xs text-muted">
        {status.panel_name} · <span className="ltr-field">{status.source_admin} → {status.target_admin}</span>
      </div>
      <div>
        <div className="mb-1 flex justify-between text-xs text-muted">
          <span>{running ? t(`panel.userDetail.transfer.phase.${status.phase}`) : t("panel.userDetail.transfer.finished")}</span>
          <span className="ltr-field">
            {formatNumber(status.processed)} / {formatNumber(status.total)}
          </span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-surface-2">
          <div className="h-full bg-primary transition-[width]" style={{ width: `${percent}%` }} />
        </div>
      </div>

      {status.job_error && <p className="rounded-md bg-danger/10 p-3 text-xs text-danger">{status.job_error}</p>}

      <dl className="divide-y divide-border/60 text-xs">
        <Row label={t("panel.userDetail.transfer.activeUsers")} value={formatNumber(status.total)} />
        <Row label={t("panel.userDetail.transfer.movedTotal")} value={formatNumber(moved)} strong />
        {(Object.keys(resultLabels) as PanelTransferResult[]).map((key) => (
          <Row key={key} label={resultLabels[key]} value={formatNumber(counts[key] || 0)} />
        ))}
        <Row label={t("panel.userDetail.transfer.skippedInactive")} value={formatNumber(status.skipped_inactive)} />
        {status.remaining_active_on_source != null && (
          <Row
            label={t("panel.userDetail.transfer.remainingOnSource")}
            value={formatNumber(status.remaining_active_on_source)}
          />
        )}
      </dl>

      {!running && (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <SelectField
              value={filter}
              onChange={(event) => setFilter(event.target.value as PanelTransferResult | "")}
              options={[
                { value: "", label: t("panel.userDetail.transfer.problemsOnly") },
                ...(Object.keys(resultLabels) as PanelTransferResult[]).map((key) => ({ value: key, label: resultLabels[key] })),
              ]}
            />
          </div>
          <div className="max-h-64 divide-y divide-border/60 overflow-y-auto rounded-md border border-border">
            {rows.length ? (
              rows.map((row) => (
                <div key={`${row.panel_user_id}-${row.result}`} className="flex flex-wrap items-center gap-2 px-3 py-2 text-xs">
                  <span className="ltr-field min-w-0 flex-1 truncate font-medium text-text">{row.username}</span>
                  {row.service_code ? <code className="ltr-field text-[11px] text-muted">#{row.service_code}</code> : null}
                  <Badge tone={RESULT_TONE[row.result]}>{resultLabels[row.result]}</Badge>
                  {row.reason && <span className="ltr-field w-full truncate text-[11px] text-muted">{row.reason}</span>}
                </div>
              ))
            ) : (
              <p className="py-4 text-center text-xs text-muted">{t("panel.userDetail.transfer.noRows")}</p>
            )}
          </div>
          <div className="flex justify-end gap-2">
            <Button size="sm" variant="secondary" onClick={() => downloadCsv(status)}>
              <Download size={14} /> {t("panel.userDetail.transfer.downloadCsv")}
            </Button>
            <Button size="sm" variant="ghost" onClick={onReset}>
              {t("panel.userDetail.transfer.newTransfer")}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

function Row({ label, value, strong = false }: { label: string; value: React.ReactNode; strong?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5">
      <dt className="text-muted">{label}</dt>
      <dd className={`ltr-field ${strong ? "font-semibold text-text" : "text-text"}`}>{value}</dd>
    </div>
  );
}

function csvCell(value: string | number | null | undefined): string {
  const text = value == null ? "" : String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function downloadCsv(status: PanelTransferStatusResponse) {
  const header = ["username", "panel_user_id", "result", "service_code", "reason"];
  const lines = status.rows.map((row: PanelTransferResultRow) =>
    [row.username, row.panel_user_id, row.result, row.service_code, row.reason].map(csvCell).join(",")
  );
  const blob = new Blob(["﻿" + [header.join(","), ...lines].join("\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `transfer_${status.source_admin || "admin"}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}
