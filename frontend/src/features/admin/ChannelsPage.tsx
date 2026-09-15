import { useState } from "react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge, Button, ErrorState, Input, Skeleton } from "../../components/ui";
import { panelChannelsApi } from "../../api/panel";
import type { PanelChannelRow, PanelLogChannelRow } from "../../types/panel";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { ConfirmButton, DataTable, SectionCard, SelectField } from "./components";
import type { Column } from "./components";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

const logTypeLabels = (t: TFunction): Record<string, string> => ({
  manual_card: t("panel.common.cardTransfer"),
  auto_card: t("panel.channels.reportAutoPayment"),
  crypto: t("panel.common.cryptoPayment"),
  stars: t("panel.channels.reportStars"),
  purchase: t("panel.channels.reportPurchase"),
  other: t("panel.channels.reportOther"),
  backup: t("panel.channels.reportBackup"),
  panel_update: t("panel.channels.reportPanelUpdate"),
  service_expiry: t("panel.channels.reportExpiry"),
  low_volume: t("panel.channels.reportLowVolume"),
  user_registration: t("panel.channels.reportSignup"),
  system_error: t("panel.channels.reportSystemError"),
  reseller: t("panel.common.reseller"),
});

const destinationLabels = (t: TFunction): Record<string, string> => ({
  channel: t("panel.channels.channel"),
  supergroup: t("panel.channels.group"),
});

const INVALIDATE = [["channels"]];

export default function AdminChannelsPage() {
  const { t } = useTranslation();
  const [channel, setChannel] = useState({ channel_id: "", title: "", link: "" });
  const [logChannel, setLogChannel] = useState({
    log_type: "",
    destination_type: "channel",
    chat_id: "",
    topic_id: "",
  });

  const query = usePanelQuery(["channels"], (auth) => panelChannelsApi.getChannels(auth));
  const createChannel = usePanelAction(panelChannelsApi.createChannel, { invalidate: INVALIDATE });
  const deleteChannel = usePanelAction(panelChannelsApi.deleteChannel, { invalidate: INVALIDATE });
  const saveLog = usePanelAction(panelChannelsApi.saveLogChannel, { invalidate: INVALIDATE });
  const deleteLog = usePanelAction(panelChannelsApi.deleteLogChannel, { invalidate: INVALIDATE });

  if (query.isError) {
    return <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />;
  }

  const logTypeOptions = [
    { value: "", label: t("panel.common.choose") },
    ...(query.data?.log_types || []).map((value) => ({ value, label: logTypeLabels(t)[value] || value })),
  ];
  const destinationOptions = (query.data?.destination_types || ["channel"]).map((value) => ({
    value,
    label: destinationLabels(t)[value] || value,
  }));

  const channelColumns: Column<PanelChannelRow>[] = [
    { key: "id", header: t("panel.common.id"), cell: (row) => <code className="ltr-field text-xs">{row.id}</code> },
    { key: "title", header: t("panel.channels.title"), cell: (row) => row.title || "—" },
    {
      key: "link",
      header: t("panel.channels.link"),
      secondary: true,
      cell: (row) =>
        row.link ? (
          <a
            href={row.link}
            target="_blank"
            rel="noopener noreferrer"
            className="ltr-field text-xs text-primary hover:underline"
          >
            {row.link}
          </a>
        ) : (
          "—"
        ),
    },
    {
      key: "actions",
      header: "",
      cell: (row) => (
        <ConfirmButton
          size="sm"
          variant="danger"
          message={t("panel.channels.channelDeleteConfirm")}
          onConfirm={() => deleteChannel.mutate({ channel_id: row.id })}
        >
          {t("common.delete")}
        </ConfirmButton>
      ),
    },
  ];

  const logColumns: Column<PanelLogChannelRow>[] = [
    { key: "type", header: t("panel.common.type"), cell: (row) => logTypeLabels(t)[row.log_type] || row.log_type },
    { key: "chat", header: t("panel.channels.chat"), cell: (row) => <code className="ltr-field text-xs">{row.chat_id ?? "—"}</code> },
    {
      key: "topic",
      header: t("panel.channels.topic"),
      secondary: true,
      cell: (row) => <code className="ltr-field text-xs">{row.topic_id ?? "—"}</code>,
    },
    {
      key: "destination",
      header: t("panel.channels.target"),
      secondary: true,
      cell: (row) => destinationLabels(t)[row.destination_type] || row.destination_type,
    },
    {
      key: "status",
      header: t("panel.common.status"),
      cell: (row) => (row.is_active ? <Badge tone="success">{t("panel.common.active")}</Badge> : <Badge tone="muted">{t("panel.common.inactive")}</Badge>),
    },
    {
      key: "actions",
      header: "",
      cell: (row) => (
        <ConfirmButton
          size="sm"
          variant="danger"
          message={t("panel.channels.targetDeleteConfirm")}
          onConfirm={() => deleteLog.mutate({ log_id: row.id })}
        >
          {t("common.delete")}
        </ConfirmButton>
      ),
    },
  ];

  return (
    <>
      <PageHeader title={t("panel.common.channels")} subtitle={t("panel.channels.subtitle")} />

      <SectionCard title={t("panel.channels.lockChannels")} description={t("panel.channels.lockNeedsSetting")}>
        {query.isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : (
          <DataTable
            columns={channelColumns}
            rows={query.data?.channels || []}
            rowKey={(row) => row.id}
            emptyTitle={t("panel.channels.channelsEmpty")}
          />
        )}
        <div className="mt-4 grid gap-3 border-t border-border pt-4 sm:grid-cols-3">
          <Input
            label={t("panel.channels.channelChatId")}
            ltr
            placeholder="-1001234567890"
            value={channel.channel_id}
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
          <div className="flex items-end">
            <Button
              loading={createChannel.isPending}
              disabled={!channel.channel_id.trim() || !channel.title.trim() || !channel.link.trim()}
              onClick={() =>
                createChannel.mutate(
                  {
                    channel_id: Number(channel.channel_id),
                    title: channel.title.trim(),
                    link: channel.link.trim(),
                  },
                  { onSuccess: () => setChannel({ channel_id: "", title: "", link: "" }) }
                )
              }
            >
              {t("panel.common.addChannel")}
            </Button>
          </div>
        </div>
        <p className="mt-2 text-xs text-muted">{t("panel.channels.botMustBeAdmin")}</p>
      </SectionCard>

      <SectionCard title={t("panel.channels.reportTargets")}>
        {query.isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : (
          <DataTable
            columns={logColumns}
            rows={query.data?.log_channels || []}
            rowKey={(row) => row.id}
            emptyTitle={t("panel.channels.targetsEmpty")}
          />
        )}
        <div className="mt-4 grid gap-3 border-t border-border pt-4 sm:grid-cols-2 lg:grid-cols-4">
          <SelectField
            label={t("panel.channels.reportType")}
            options={logTypeOptions}
            value={logChannel.log_type}
            onChange={(event) => setLogChannel({ ...logChannel, log_type: event.target.value })}
          />
          <SelectField
            label={t("panel.channels.targetType")}
            options={destinationOptions}
            value={logChannel.destination_type}
            onChange={(event) => setLogChannel({ ...logChannel, destination_type: event.target.value })}
          />
          <Input
            label={t("panel.channels.targetChatId")}
            ltr
            value={logChannel.chat_id}
            onChange={(event) => setLogChannel({ ...logChannel, chat_id: event.target.value })}
          />
          <Input
            label={t("panel.channels.topicId")}
            ltr
            inputMode="numeric"
            value={logChannel.topic_id}
            onChange={(event) => setLogChannel({ ...logChannel, topic_id: event.target.value })}
          />
          <div className="flex items-end">
            <Button
              loading={saveLog.isPending}
              disabled={!logChannel.log_type || !logChannel.chat_id.trim()}
              onClick={() =>
                saveLog.mutate(
                  {
                    log_type: logChannel.log_type,
                    destination_type: logChannel.destination_type,
                    chat_id: Number(logChannel.chat_id),
                    topic_id: logChannel.topic_id.trim() ? Number(logChannel.topic_id) : null,
                  },
                  {
                    onSuccess: () =>
                      setLogChannel({ log_type: "", destination_type: "channel", chat_id: "", topic_id: "" }),
                  }
                )
              }
            >
              {t("panel.channels.addTarget")}
            </Button>
          </div>
        </div>
      </SectionCard>
    </>
  );
}
