import { useState } from "react";
import {
  Building2,
  Coins,
  CreditCard,
  Database,
  Gift,
  List,
  Package,
  Pencil,
  Radio,
  RefreshCw,
  ShoppingBag,
  Star,
  Zap,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge, Button, ErrorState, IconBadge, Input, Skeleton } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";
import { panelChannelsApi } from "../../api/panel";
import type { PanelChannelRow, PanelLogChannelRow } from "../../types/panel";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { useWebAppAuth } from "../../hooks/useWebAppAuth";
import { ConfirmButton, SectionCard, StatTile } from "./components";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

// Covers every value app.logger.tags.LogType has ever had, so a legacy row
// saved before the picker was narrowed to ALL_LOG_TYPES still shows a real
// label instead of the raw snake_case string.
const logTypeLabels = (t: TFunction): Record<string, string> => ({
  manual_card: t("panel.channels.reportManualCard"),
  auto_card: t("panel.channels.reportAutoPayment"),
  crypto: t("panel.channels.reportCrypto"),
  stars: t("panel.channels.reportStars"),
  purchase: t("panel.channels.reportPurchase"),
  renew: t("panel.channels.reportRenew"),
  trial: t("panel.channels.reportTrial"),
  reseller: t("panel.channels.reportReseller"),
  user_registration: t("panel.channels.reportSignup"),
  backup: t("panel.channels.reportBackup"),
  account_replacement: t("panel.channels.reportAccountReplacement"),
  system_error: t("panel.channels.reportSystemError"),
  panel_update: t("panel.channels.reportPanelUpdate"),
  service_expiry: t("panel.channels.reportExpiry"),
  low_volume: t("panel.channels.reportLowVolume"),
  transaction_approved: t("panel.channels.reportTransactionApproved"),
  transaction_rejected: t("panel.channels.reportTransactionRejected"),
  transaction_expired: t("panel.channels.reportTransactionExpired"),
  service_created: t("panel.channels.reportServiceCreated"),
  service_deleted: t("panel.channels.reportServiceDeleted"),
  service_renewed: t("panel.channels.reportServiceRenewed"),
  app_files: t("panel.channels.reportAppFiles"),
  other: t("panel.channels.reportOther"),
});

const destinationLabels = (t: TFunction): Record<string, string> => ({
  channel: t("panel.channels.channel"),
  supergroup: t("panel.channels.group"),
});

// Icon per report type — mirrors the bot's own "مدیریت لاگ‌ها" Telegram menu
// (app/telegram/admin/logs/states.py: ALL_LOG_TYPES), which is also where
// the picker's actual option list comes from (query.data.log_types).
const REPORT_TYPE_ICONS: Record<string, LucideIcon> = {
  manual_card: CreditCard,
  auto_card: Zap,
  crypto: Coins,
  reseller: Building2,
  stars: Star,
  account_replacement: RefreshCw,
  other: List,
  app_files: Package,
  backup: Database,
  purchase: ShoppingBag,
  renew: RefreshCw,
  trial: Gift,
};

function reportIcon(logType: string): LucideIcon {
  return REPORT_TYPE_ICONS[logType] ?? List;
}

const INVALIDATE = [["channels"]];

export default function AdminChannelsPage() {
  const { t } = useTranslation();
  const { auth } = useWebAppAuth();
  const toast = useToast();
  const queryClient = useQueryClient();

  const [channel, setChannel] = useState({ channel_id: "", title: "", link: "" });
  const [editingChannelId, setEditingChannelId] = useState<number | null>(null);

  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set());
  const [destinationType, setDestinationType] = useState<"channel" | "supergroup">("channel");
  const [chatId, setChatId] = useState("");
  const [topicId, setTopicId] = useState("");
  const [editingLog, setEditingLog] = useState<PanelLogChannelRow | null>(null);
  const [bulkSaving, setBulkSaving] = useState(false);

  const query = usePanelQuery(["channels"], (a) => panelChannelsApi.getChannels(a));
  const createChannel = usePanelAction(panelChannelsApi.createChannel, { invalidate: INVALIDATE });
  const deleteChannel = usePanelAction(panelChannelsApi.deleteChannel, { invalidate: INVALIDATE });
  const deleteLog = usePanelAction(panelChannelsApi.deleteLogChannel, { invalidate: INVALIDATE });

  if (query.isError) {
    return <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />;
  }

  const channels = query.data?.channels || [];
  const logChannels = query.data?.log_channels || [];
  const reportTypes = query.data?.log_types || [];
  const activeCount = logChannels.filter((row) => row.is_active).length;
  const inactiveCount = logChannels.length - activeCount;

  function resetChannelForm() {
    setChannel({ channel_id: "", title: "", link: "" });
    setEditingChannelId(null);
  }
  function startEditChannel(row: PanelChannelRow) {
    setEditingChannelId(row.id);
    setChannel({ channel_id: String(row.id), title: row.title || "", link: row.link || "" });
  }
  function handleChannelSubmit() {
    const channelId = editingChannelId ?? Number(channel.channel_id);
    if (!channelId || !channel.title.trim() || !channel.link.trim()) return;
    createChannel.mutate(
      { channel_id: channelId, title: channel.title.trim(), link: channel.link.trim() },
      { onSuccess: resetChannelForm }
    );
  }

  function resetLogForm() {
    setSelectedTypes(new Set());
    setDestinationType("channel");
    setChatId("");
    setTopicId("");
    setEditingLog(null);
  }
  function startEditLog(row: PanelLogChannelRow) {
    setEditingLog(row);
    setSelectedTypes(new Set([row.log_type]));
    setDestinationType(row.destination_type === "supergroup" ? "supergroup" : "channel");
    setChatId(row.chat_id != null ? String(row.chat_id) : "");
    setTopicId(row.topic_id != null ? String(row.topic_id) : "");
  }
  function toggleType(value: string) {
    if (editingLog) return;
    setSelectedTypes((prev) => {
      const next = new Set(prev);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
  }

  async function handleLogSubmit() {
    if (!auth || !selectedTypes.size || !chatId.trim()) return;
    setBulkSaving(true);
    try {
      const parsedChat = Number(chatId);
      const parsedTopic = topicId.trim() ? Number(topicId) : null;
      await Promise.all(
        [...selectedTypes].map((log_type) =>
          panelChannelsApi.saveLogChannel({
            ...auth,
            log_type,
            destination_type: destinationType,
            chat_id: parsedChat,
            topic_id: parsedTopic,
          })
        )
      );
      toast.show(
        editingLog ? t("panel.channels.updateTarget") : t("panel.channels.targetsSaved", { count: selectedTypes.size }),
        "success"
      );
      void queryClient.invalidateQueries({ queryKey: ["panel", "channels"] });
      resetLogForm();
    } catch (error) {
      toast.show(error instanceof Error ? error.message : "عملیات انجام نشد", "error");
    } finally {
      setBulkSaving(false);
    }
  }

  return (
    <>
      <PageHeader title={t("panel.common.channels")} subtitle={t("panel.channels.subtitle")} />

      <div className="grid gap-3 sm:grid-cols-3">
        <StatTile label={t("panel.channels.statLockChannels")} value={channels.length} icon={Radio} />
        <StatTile
          label={t("panel.channels.statActiveTargets")}
          value={`${activeCount} / ${logChannels.length}`}
          icon={Package}
          tone="success"
        />
        <StatTile label={t("panel.channels.statInactiveTargets")} value={inactiveCount} icon={List} tone={inactiveCount ? "warning" : "default"} />
      </div>

      <SectionCard title={t("panel.channels.lockChannels")} description={t("panel.channels.lockNeedsSetting")}>
        {query.isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : channels.length ? (
          <div className="divide-y divide-border/60">
            {channels.map((row) => (
              <div
                key={row.id}
                className={`flex flex-wrap items-center gap-3 py-3 first:pt-0 last:pb-0 ${
                  editingChannelId === row.id ? "-mx-2 rounded-lg bg-primary/5 px-2" : ""
                }`}
              >
                <IconBadge icon={Radio} tone="primary" size="sm" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-text">{row.title || "—"}</p>
                  <p className="truncate text-xs text-muted">
                    <span className="ltr-field">{row.id}</span>
                    {row.link && (
                      <>
                        {" · "}
                        <a href={row.link} target="_blank" rel="noopener noreferrer" className="ltr-field text-primary hover:underline">
                          {row.link}
                        </a>
                      </>
                    )}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <Button variant="ghost" size="sm" className="!px-2" title={t("panel.channels.editChannel")} onClick={() => startEditChannel(row)}>
                    <Pencil size={14} />
                  </Button>
                  <ConfirmButton
                    size="sm"
                    variant="ghost"
                    className="!px-2 text-danger hover:bg-danger/10"
                    message={t("panel.channels.channelDeleteConfirm")}
                    onConfirm={() => deleteChannel.mutate({ channel_id: row.id })}
                  >
                    {t("common.delete")}
                  </ConfirmButton>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="py-4 text-center text-sm text-muted">{t("panel.channels.channelsEmpty")}</p>
        )}

        {editingChannelId != null && (
          <div className="mt-4 flex items-center gap-2 rounded-lg border border-primary/20 bg-primary/5 px-3 py-2 text-xs">
            <Pencil size={14} className="text-primary" />
            <span>{t("panel.channels.editingChannel", { title: channel.title })}</span>
            <button className="mr-auto text-xs font-semibold text-primary hover:underline" onClick={resetChannelForm}>
              {t("panel.channels.cancelEdit")}
            </button>
          </div>
        )}
        <div className="mt-4 grid gap-3 border-t border-border pt-4 sm:grid-cols-2 lg:grid-cols-3">
          <Input
            label={t("panel.channels.channelChatId")}
            ltr
            placeholder="-1001234567890"
            value={channel.channel_id}
            disabled={editingChannelId != null}
            onChange={(event) => setChannel({ ...channel, channel_id: event.target.value })}
          />
          <Input
            label={t("panel.channels.title")}
            value={channel.title}
            onChange={(event) => setChannel({ ...channel, title: event.target.value })}
          />
          <Input
            label={t("panel.channels.link")}
            ltr
            placeholder="https://t.me/..."
            value={channel.link}
            onChange={(event) => setChannel({ ...channel, link: event.target.value })}
          />
          <div className="flex items-end sm:col-span-2 lg:col-span-1">
            <Button
              fullWidth
              loading={createChannel.isPending}
              disabled={!channel.channel_id.trim() || !channel.title.trim() || !channel.link.trim()}
              onClick={handleChannelSubmit}
            >
              {editingChannelId != null ? t("panel.channels.updateChannel") : t("panel.common.addChannel")}
            </Button>
          </div>
        </div>
        <p className="mt-2 text-xs text-muted">{t("panel.channels.botMustBeAdmin")}</p>
      </SectionCard>

      <SectionCard title={t("panel.channels.reportTargets")}>
        {query.isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : logChannels.length ? (
          <div className="divide-y divide-border/60">
            {logChannels.map((row) => {
              const Icon = reportIcon(row.log_type);
              return (
                <div
                  key={row.id}
                  className={`flex flex-wrap items-center gap-3 py-3 first:pt-0 last:pb-0 ${
                    editingLog?.id === row.id ? "-mx-2 rounded-lg bg-primary/5 px-2" : ""
                  }`}
                >
                  <IconBadge icon={Icon} tone="muted" size="sm" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-text">{logTypeLabels(t)[row.log_type] || row.log_type}</p>
                    <p className="truncate text-xs text-muted">
                      {destinationLabels(t)[row.destination_type] || row.destination_type}
                      {" · "}
                      <span className="ltr-field">{row.chat_id ?? "—"}</span>
                      {row.topic_id != null && <span className="ltr-field"> / {row.topic_id}</span>}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {row.is_active ? (
                      <Badge tone="success">{t("panel.common.active")}</Badge>
                    ) : (
                      <Badge tone="muted">{t("panel.common.inactive")}</Badge>
                    )}
                    <Button variant="ghost" size="sm" className="!px-2" title={t("panel.channels.editTarget")} onClick={() => startEditLog(row)}>
                      <Pencil size={14} />
                    </Button>
                    <ConfirmButton
                      size="sm"
                      variant="ghost"
                      className="!px-2 text-danger hover:bg-danger/10"
                      message={t("panel.channels.targetDeleteConfirm")}
                      onConfirm={() => deleteLog.mutate({ log_id: row.id })}
                    >
                      {t("common.delete")}
                    </ConfirmButton>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="py-4 text-center text-sm text-muted">{t("panel.channels.targetsEmpty")}</p>
        )}

        <div className="mt-4 border-t border-border pt-4">
          {editingLog && (
            <div className="mb-3 flex flex-wrap items-center gap-2 rounded-lg border border-primary/20 bg-primary/5 px-3 py-2 text-xs">
              <Pencil size={14} className="text-primary" />
              <span>{t("panel.channels.editingTarget", { type: logTypeLabels(t)[editingLog.log_type] || editingLog.log_type })}</span>
              <button className="mr-auto text-xs font-semibold text-primary hover:underline" onClick={resetLogForm}>
                {t("panel.channels.cancelEdit")}
              </button>
            </div>
          )}

          <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2">
            <span className="text-xs font-semibold text-muted">{t("panel.channels.reportTypeMultiHint")}</span>
            {!editingLog && (
              <div className="flex gap-3">
                <button
                  className="text-xs font-semibold text-primary hover:underline disabled:cursor-not-allowed disabled:text-muted disabled:no-underline"
                  disabled={!reportTypes.length}
                  onClick={() => setSelectedTypes(new Set(reportTypes))}
                >
                  {t("panel.channels.selectAll")}
                </button>
                <button
                  className="text-xs font-semibold text-primary hover:underline disabled:cursor-not-allowed disabled:text-muted disabled:no-underline"
                  disabled={!selectedTypes.size}
                  onClick={() => setSelectedTypes(new Set())}
                >
                  {t("panel.channels.clearSelection")}
                </button>
              </div>
            )}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {reportTypes.map((value) => {
              const Icon = reportIcon(value);
              const active = selectedTypes.has(value);
              const disabled = editingLog != null && !active;
              return (
                <button
                  key={value}
                  type="button"
                  disabled={disabled}
                  onClick={() => toggleType(value)}
                  className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-35 ${
                    active
                      ? "border-primary bg-primary text-primary-text"
                      : "border-border text-text hover:border-primary/50"
                  }`}
                >
                  <Icon size={13} />
                  {logTypeLabels(t)[value] || value}
                </button>
              );
            })}
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="block text-sm">
              <span className="mb-1.5 block text-muted">{t("panel.channels.targetType")}</span>
              <div className="flex h-11 rounded-md border border-border bg-surface p-1">
                {(["channel", "supergroup"] as const).map((value) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setDestinationType(value)}
                    className={`flex-1 rounded text-sm font-medium transition-colors ${
                      destinationType === value ? "bg-primary text-primary-text" : "text-muted hover:text-text"
                    }`}
                  >
                    {destinationLabels(t)[value]}
                  </button>
                ))}
              </div>
            </div>
            <Input label={t("panel.channels.targetChatId")} ltr value={chatId} onChange={(event) => setChatId(event.target.value)} />
            <Input
              label={t("panel.channels.topicId")}
              ltr
              inputMode="numeric"
              value={topicId}
              onChange={(event) => setTopicId(event.target.value)}
            />
            <div className="flex items-end">
              <Button
                fullWidth
                loading={bulkSaving}
                disabled={!selectedTypes.size || !chatId.trim()}
                onClick={handleLogSubmit}
              >
                {editingLog
                  ? t("panel.channels.updateTarget")
                  : selectedTypes.size
                    ? t("panel.channels.addTargetCount", { count: selectedTypes.size })
                    : t("panel.channels.addTarget")}
              </Button>
            </div>
          </div>
        </div>
      </SectionCard>
    </>
  );
}
