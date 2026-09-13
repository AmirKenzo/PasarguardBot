import { useEffect, useState } from "react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge, Button, ErrorState, Input, Pagination, Skeleton } from "../../components/ui";
import { formatNumber, formatToman, formatUnixDate } from "../../lib/format";
import { panelReferralApi } from "../../api/panel";
import type { PanelReferralRewardRow } from "../../types/panel";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { DataTable, SectionCard, StatTile, Toggle } from "./components";
import type { Column } from "./components";
import { useTranslation } from "react-i18next";

interface Draft {
  referral_enabled: boolean;
  referral_reward_amount: string;
  referral_bonus_amount: string;
  referral_banner_text: string;
}

export default function AdminReferralPage() {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const [draft, setDraft] = useState<Draft | null>(null);

  const query = usePanelQuery(["referral", page], (auth) =>
    panelReferralApi.getReferral({ ...auth, page, limit: 25 })
  );
  const save = usePanelAction(panelReferralApi.saveReferral, { invalidate: [["referral"]] });

  const settings = query.data?.settings;

  useEffect(() => {
    if (!settings || draft !== null) return;
    setDraft({
      referral_enabled: settings.referral_enabled,
      referral_reward_amount: String(settings.referral_reward_amount),
      referral_bonus_amount: String(settings.referral_bonus_amount),
      referral_banner_text: settings.referral_banner_text || "",
    });
  }, [settings, draft]);

  const columns: Column<PanelReferralRewardRow>[] = [
    {
      key: "referrer",
      header: t("panel.referral.referrer"),
      cell: (row) => <code className="ltr-field text-xs">{row.referrer_id ?? "—"}</code>,
    },
    {
      key: "referred",
      header: t("panel.referral.invitee"),
      cell: (row) => <code className="ltr-field text-xs">{row.referred_id ?? "—"}</code>,
    },
    { key: "reward", header: t("panel.referral.referrerReward"), cell: (row) => formatToman(row.reward_amount) },
    { key: "bonus", header: t("panel.referral.inviteeGift"), secondary: true, cell: (row) => formatToman(row.bonus_amount) },
    {
      key: "status",
      header: t("panel.common.status"),
      cell: (row) =>
        row.status === "completed" ? <Badge tone="success">{t("panel.referral.paid")}</Badge> : <Badge tone="muted">{row.status || "—"}</Badge>,
    },
    {
      key: "created",
      header: t("panel.referral.date"),
      secondary: true,
      cell: (row) => (
        <span className="text-xs text-muted">{row.created_at ? formatUnixDate(row.created_at) : "—"}</span>
      ),
    },
  ];

  if (query.isError) {
    return <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />;
  }

  return (
    <>
      <PageHeader title={t("panel.common.referral")} subtitle={t("panel.referral.subtitle")} />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
        <StatTile label={t("panel.referral.totalRewardedInvites")} value={formatNumber(query.data?.total_rewarded || 0)} />
        <StatTile label={t("panel.referral.totalReferrerRewards")} value={formatToman(query.data?.total_paid || 0)} tone="primary" />
        <StatTile label={t("panel.referral.totalInviteeGifts")} value={formatToman(query.data?.total_bonus || 0)} />
      </div>

      <SectionCard title={t("panel.referral.settingsTitle")}>
        {!draft ? (
          <Skeleton className="h-40 w-full" />
        ) : (
          <div className="space-y-3">
            <Toggle
              checked={draft.referral_enabled}
              onChange={(referral_enabled) => setDraft({ ...draft, referral_enabled })}
              label={t("panel.referral.enabled")}
            />
            <div className="grid gap-3 sm:grid-cols-2">
              <Input
                label={t("panel.referral.referrerRewardAmount")}
                inputMode="numeric"
                value={draft.referral_reward_amount}
                onChange={(event) => setDraft({ ...draft, referral_reward_amount: event.target.value })}
              />
              <Input
                label={t("panel.referral.inviteeGiftAmount")}
                inputMode="numeric"
                value={draft.referral_bonus_amount}
                onChange={(event) => setDraft({ ...draft, referral_bonus_amount: event.target.value })}
              />
            </div>
            <label className="block text-sm">
              <span className="mb-1.5 block text-muted">{t("panel.referral.bannerText")}</span>
              <textarea
                rows={4}
                value={draft.referral_banner_text}
                onChange={(event) => setDraft({ ...draft, referral_banner_text: event.target.value })}
                className="w-full rounded-md border border-border bg-surface p-3 text-text outline-none focus:border-primary focus:ring-4 focus:ring-primary/10"
              />
            </label>
            <div className="flex justify-end">
              <Button
                size="sm"
                loading={save.isPending}
                onClick={() =>
                  save.mutate({
                    referral_enabled: draft.referral_enabled,
                    referral_reward_amount: Number(draft.referral_reward_amount) || 0,
                    referral_bonus_amount: Number(draft.referral_bonus_amount) || 0,
                    referral_banner_text: draft.referral_banner_text,
                  })
                }
              >
                {t("panel.referral.saveSettings")}
              </Button>
            </div>
          </div>
        )}
      </SectionCard>

      <SectionCard title={t("panel.referral.rewardHistory")}>
        <DataTable
          columns={columns}
          rows={query.data?.rewards || []}
          rowKey={(row) => row.id}
          loading={query.isLoading}
          emptyTitle={t("panel.referral.empty")}
        />
        <div className="mt-4">
          <Pagination page={page} totalPages={query.data?.meta.total_pages || 1} onChange={setPage} />
        </div>
      </SectionCard>
    </>
  );
}
