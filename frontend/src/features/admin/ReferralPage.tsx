import { useEffect, useState } from "react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge, Button, ErrorState, Input, Pagination, Skeleton } from "../../components/ui";
import { formatNumber, formatToman, formatUnixDate } from "../../lib/format";
import { panelReferralApi } from "../../api/panel";
import type { PanelReferralPayoutRow, PanelReferralRewardRow } from "../../types/panel";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { SegmentedControl } from "../../components/ui/Select";
import { DataTable, SectionCard, StatTile, Toggle } from "./components";
import type { Column } from "./components";
import { useTranslation } from "react-i18next";

interface Draft {
  referral_enabled: boolean;
  referral_reward_amount: string;
  referral_reward_mode: "fixed" | "percent";
  referral_reward_percent: string;
  referral_reward_max: string;
  referral_bonus_amount: string;
  referral_bonus_mode: "fixed" | "percent";
  referral_bonus_percent: string;
  referral_bonus_max: string;
  referral_reward_destination: "wallet" | "earnings";
  referral_withdraw_enabled: boolean;
  referral_withdraw_min: string;
  referral_transfer_enabled: boolean;
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
      referral_reward_mode: settings.referral_reward_mode ?? "fixed",
      referral_reward_percent: String(settings.referral_reward_percent ?? 10),
      referral_reward_max: String(settings.referral_reward_max ?? 0),
      referral_bonus_amount: String(settings.referral_bonus_amount),
      referral_bonus_mode: settings.referral_bonus_mode ?? "fixed",
      referral_bonus_percent: String(settings.referral_bonus_percent ?? 5),
      referral_bonus_max: String(settings.referral_bonus_max ?? 0),
      referral_reward_destination: settings.referral_reward_destination ?? "wallet",
      referral_withdraw_enabled: Boolean(settings.referral_withdraw_enabled),
      referral_withdraw_min: String(settings.referral_withdraw_min ?? 0),
      referral_transfer_enabled: settings.referral_transfer_enabled ?? true,
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
    {
      key: "reward",
      header: t("panel.referral.referrerReward"),
      cell: (row) => (
        <div>
          {formatToman(row.reward_amount)}
          {row.reward_percent != null && row.base_amount != null && (
            <p className="text-[11px] text-muted">
              {t("panel.referral.rewardOfPurchase", { percent: row.reward_percent, amount: formatToman(row.base_amount) })}
            </p>
          )}
        </div>
      ),
    },
    {
      key: "bonus",
      header: t("panel.referral.inviteeGift"),
      secondary: true,
      cell: (row) => (
        <div>
          {formatToman(row.bonus_amount)}
          {row.bonus_percent != null && row.base_amount != null && (
            <p className="text-[11px] text-muted">
              {t("panel.referral.rewardOfPurchase", { percent: row.bonus_percent, amount: formatToman(row.base_amount) })}
            </p>
          )}
        </div>
      ),
    },
    {
      key: "status",
      header: t("panel.common.status"),
      cell: (row) => (
        <Badge tone={REWARD_STATUS_TONES[row.status || ""] ?? "muted"}>
          {t(`panel.referral.rewardStatus.${row.status}`, { defaultValue: row.status || "—" })}
        </Badge>
      ),
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
            <SidePayoutFields
              title={t("panel.referral.rewardMode")}
              fixedLabel={t("panel.referral.referrerRewardAmount")}
              mode={draft.referral_reward_mode}
              amount={draft.referral_reward_amount}
              percent={draft.referral_reward_percent}
              max={draft.referral_reward_max}
              onChange={(next) =>
                setDraft({
                  ...draft,
                  referral_reward_mode: next.mode,
                  referral_reward_amount: next.amount,
                  referral_reward_percent: next.percent,
                  referral_reward_max: next.max,
                })
              }
            />
            <SidePayoutFields
              title={t("panel.referral.bonusMode")}
              fixedLabel={t("panel.referral.inviteeGiftAmount")}
              mode={draft.referral_bonus_mode}
              amount={draft.referral_bonus_amount}
              percent={draft.referral_bonus_percent}
              max={draft.referral_bonus_max}
              onChange={(next) =>
                setDraft({
                  ...draft,
                  referral_bonus_mode: next.mode,
                  referral_bonus_amount: next.amount,
                  referral_bonus_percent: next.percent,
                  referral_bonus_max: next.max,
                })
              }
            />
            <p className="text-xs text-muted">{t("panel.referral.rewardModeHint")}</p>
            <div className="space-y-3 rounded-lg border border-border p-3">
              <span className="block text-sm text-muted">{t("panel.referral.destination")}</span>
              <SegmentedControl
                options={[
                  { value: "wallet", label: t("panel.referral.destinationWallet") },
                  { value: "earnings", label: t("panel.referral.destinationEarnings") },
                ]}
                value={draft.referral_reward_destination}
                onChange={(value) =>
                  setDraft({ ...draft, referral_reward_destination: value === "earnings" ? "earnings" : "wallet" })
                }
              />
              <p className="text-xs text-muted">{t("panel.referral.destinationHint")}</p>
              {draft.referral_reward_destination === "earnings" && (
                <div className="space-y-3">
                  <Toggle
                    checked={draft.referral_withdraw_enabled}
                    onChange={(referral_withdraw_enabled) => setDraft({ ...draft, referral_withdraw_enabled })}
                    label={t("panel.referral.withdrawEnabled")}
                  />
                  <Input
                    label={t("panel.referral.withdrawMin")}
                    inputMode="numeric"
                    value={draft.referral_withdraw_min}
                    onChange={(event) => setDraft({ ...draft, referral_withdraw_min: event.target.value })}
                  />
                  <Toggle
                    checked={draft.referral_transfer_enabled}
                    onChange={(referral_transfer_enabled) => setDraft({ ...draft, referral_transfer_enabled })}
                    label={t("panel.referral.transferEnabled")}
                  />
                </div>
              )}
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
                    referral_reward_mode: draft.referral_reward_mode,
                    referral_reward_percent: Math.min(100, Math.max(1, Number(draft.referral_reward_percent) || 10)),
                    referral_reward_max: Math.max(0, Number(draft.referral_reward_max) || 0),
                    referral_bonus_amount: Number(draft.referral_bonus_amount) || 0,
                    referral_bonus_mode: draft.referral_bonus_mode,
                    referral_bonus_percent: Math.min(100, Math.max(1, Number(draft.referral_bonus_percent) || 5)),
                    referral_bonus_max: Math.max(0, Number(draft.referral_bonus_max) || 0),
                    referral_reward_destination: draft.referral_reward_destination,
                    referral_withdraw_enabled: draft.referral_withdraw_enabled,
                    referral_withdraw_min: Math.max(0, Number(draft.referral_withdraw_min) || 0),
                    referral_transfer_enabled: draft.referral_transfer_enabled,
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

      <PayoutsSection />

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

interface SidePayout {
  mode: "fixed" | "percent";
  amount: string;
  percent: string;
  max: string;
}

/** One side of a referral (referrer reward or invitee bonus): fixed amount or a capped percent. */
function SidePayoutFields({
  title,
  fixedLabel,
  onChange,
  ...value
}: SidePayout & { title: string; fixedLabel: string; onChange: (next: SidePayout) => void }) {
  const { t } = useTranslation();
  return (
    <div className="space-y-2 rounded-lg border border-border p-3">
      <span className="block text-sm text-muted">{title}</span>
      <SegmentedControl
        options={[
          { value: "fixed", label: t("panel.referral.rewardFixed") },
          { value: "percent", label: t("panel.referral.rewardPercent") },
        ]}
        value={value.mode}
        onChange={(mode) => onChange({ ...value, mode: mode === "percent" ? "percent" : "fixed" })}
      />
      <div className="grid gap-3 sm:grid-cols-2">
        {value.mode === "percent" ? (
          <>
            <Input
              label={t("panel.referral.rewardPercentLabel")}
              inputMode="numeric"
              value={value.percent}
              onChange={(event) => onChange({ ...value, percent: event.target.value })}
            />
            <Input
              label={t("panel.referral.rewardMaxLabel")}
              inputMode="numeric"
              value={value.max}
              onChange={(event) => onChange({ ...value, max: event.target.value })}
            />
          </>
        ) : (
          <Input
            label={fixedLabel}
            inputMode="numeric"
            value={value.amount}
            onChange={(event) => onChange({ ...value, amount: event.target.value })}
          />
        )}
      </div>
    </div>
  );
}

// "completed" means credited straight to the wallet; the rest are earnings states.
const REWARD_STATUS_TONES: Record<string, "success" | "warning" | "muted" | "primary"> = {
  completed: "success",
  available: "primary",
  requested: "warning",
  paid: "success",
  converted: "muted",
};

const PAYOUT_STATUS_TONES: Record<string, "success" | "warning" | "danger" | "muted"> = {
  pending: "warning",
  paid: "success",
  rejected: "danger",
  completed: "muted",
};

/** Referral earnings cash-outs: card withdrawals waiting for an admin, and wallet transfers. */
function PayoutsSection() {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("pending");
  const query = usePanelQuery(["referral-payouts", status, page], (auth) =>
    panelReferralApi.getReferralPayouts({ ...auth, status, page, limit: 25 })
  );
  const settle = usePanelAction(panelReferralApi.settleReferralPayout, {
    invalidate: [["referral-payouts"], ["referral"]],
  });

  const columns: Column<PanelReferralPayoutRow>[] = [
    { key: "id", header: "#", cell: (row) => <code className="ltr-field text-xs">{row.id}</code> },
    { key: "user", header: t("panel.referral.referrer"), cell: (row) => <code className="ltr-field text-xs">{row.user_id}</code> },
    { key: "amount", header: t("panel.referral.payoutAmount"), cell: (row) => formatToman(row.amount) },
    {
      key: "card",
      header: t("panel.referral.payoutCard"),
      cell: (row) =>
        row.method === "wallet" ? (
          <span className="text-xs text-muted">{t("panel.referral.payoutToWallet")}</span>
        ) : (
          <div>
            <code className="ltr-field text-xs">{row.card_number}</code>
            <p className="text-[11px] text-muted">{row.card_holder}</p>
          </div>
        ),
    },
    {
      key: "status",
      header: t("panel.common.status"),
      cell: (row) => (
        <Badge tone={PAYOUT_STATUS_TONES[row.status] ?? "muted"}>
          {t(`panel.referral.payoutStatus.${row.status}`, { defaultValue: row.status })}
        </Badge>
      ),
    },
    {
      key: "created",
      header: t("panel.referral.date"),
      secondary: true,
      cell: (row) => <span className="text-xs text-muted">{row.created_at ? formatUnixDate(row.created_at) : "—"}</span>,
    },
    {
      key: "actions",
      header: "",
      cell: (row) =>
        row.status === "pending" ? (
          <div className="flex gap-1.5">
            <Button size="sm" loading={settle.isPending} onClick={() => settle.mutate({ id: row.id, paid: true })}>
              {t("panel.referral.markPaid")}
            </Button>
            <Button
              size="sm"
              variant="secondary"
              loading={settle.isPending}
              onClick={() => settle.mutate({ id: row.id, paid: false })}
            >
              {t("panel.referral.reject")}
            </Button>
          </div>
        ) : null,
    },
  ];

  return (
    <SectionCard title={`${t("panel.referral.payoutsTitle")} (${query.data?.pending_count ?? 0})`}>
      <div className="mb-3">
        <SegmentedControl
          options={[
            { value: "pending", label: t("panel.referral.payoutStatus.pending") },
            { value: "", label: t("panel.referral.allPayouts") },
          ]}
          value={status}
          onChange={(value) => {
            setStatus(value);
            setPage(1);
          }}
        />
      </div>
      <DataTable
        columns={columns}
        rows={query.data?.payouts || []}
        rowKey={(row) => row.id}
        loading={query.isLoading}
        emptyTitle={t("panel.referral.noPayouts")}
      />
      <div className="mt-4">
        <Pagination page={page} totalPages={query.data?.meta.total_pages || 1} onChange={setPage} />
      </div>
    </SectionCard>
  );
}
