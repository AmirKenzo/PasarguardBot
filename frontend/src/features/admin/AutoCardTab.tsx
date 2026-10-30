import { useEffect, useState } from "react";
import { CheckCircle2, Clock, Eye, EyeOff, RefreshCw, Wallet, Zap } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Card, CopyField, ErrorState, Input, Skeleton } from "../../components/ui";
import { SegmentedControl } from "../../components/ui/Select";
import { useToast } from "../../components/ui/Toast";
import { panelPaymentsApi } from "../../api/panel";
import { formatNumber, formatToman } from "../../lib/format";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import type { PanelAutoCardResponse, PanelAutoCardVisibility } from "../../types/panel";
import { ConfirmButton, SectionCard, StatTile, Toggle } from "./components";

const QUERY_KEY = ["payments", "auto-card"];

type Forwarder = "forapp" | "smsforwarder";

const GUIDE_STEPS: Record<Forwarder, number> = { forapp: 5, smsforwarder: 4 };
const SMS_FORWARDER_TEMPLATE = '{"text":"[org_content]","from":"[from]","timestamp":"[timestamp]"}';

interface Draft {
  enabled: boolean;
  visibility: PanelAutoCardVisibility;
  card_number: string;
  card_name: string;
  deposit_min: string;
  deposit_max: string;
  bonus_enabled: boolean;
  bonus_percent: string;
}

function toDraft(data: PanelAutoCardResponse): Draft {
  return {
    enabled: data.enabled,
    visibility: data.visibility,
    card_number: data.card_number,
    card_name: data.card_name,
    deposit_min: String(data.deposit_min),
    deposit_max: String(data.deposit_max),
    bonus_enabled: data.bonus_enabled,
    bonus_percent: String(data.bonus_percent),
  };
}

function digits(value: string): string {
  return value.replace(/\D/g, "");
}

function maskKey(key: string): string {
  return key.length <= 8 ? "••••••••" : `${key.slice(0, 4)}••••••••${key.slice(-4)}`;
}

export default function AutoCardTab() {
  const { t } = useTranslation();
  const { show } = useToast();
  const query = usePanelQuery(QUERY_KEY, (auth) => panelPaymentsApi.getAutoCard(auth));
  const save = usePanelAction(panelPaymentsApi.saveAutoCard, { invalidate: [QUERY_KEY] });
  const rotate = usePanelAction(panelPaymentsApi.rotateAutoCardKey, { invalidate: [QUERY_KEY] });
  const [draft, setDraft] = useState<Draft | null>(null);
  const [showKey, setShowKey] = useState(false);
  const [app, setApp] = useState<Forwarder>("forapp");

  useEffect(() => {
    if (query.data) setDraft(toDraft(query.data));
  }, [query.data]);

  if (query.isError) {
    return <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />;
  }
  if (query.isLoading || !query.data || !draft) {
    return <Skeleton className="h-96 w-full" />;
  }

  const data = query.data;
  const ready = data.enabled && !!data.card_number && !!data.api_key;

  const handleSave = () => {
    const min = Number(digits(draft.deposit_min)) || 0;
    const max = Number(digits(draft.deposit_max)) || 0;
    if (max < min) {
      show(t("panel.autoCard.rangeError"), "error");
      return;
    }
    save.mutate({
      enabled: draft.enabled,
      visibility: draft.visibility,
      card_number: draft.card_number.trim(),
      card_name: draft.card_name.trim(),
      deposit_min: min,
      deposit_max: max,
      bonus_enabled: draft.bonus_enabled,
      bonus_percent: Math.min(100, Number(digits(draft.bonus_percent)) || 0),
    });
  };

  const statusTone = ready ? "success" : data.enabled ? "warning" : "muted";
  const statusText = ready
    ? t("panel.autoCard.statusActive")
    : data.enabled
      ? t("panel.autoCard.statusIncomplete")
      : t("panel.autoCard.statusOff");

  return (
    <div className="space-y-4">
      <Card className="flex flex-wrap items-center gap-3 p-4">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-sm bg-primary/10 text-primary">
          <Zap size={22} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-text">{t("panel.autoCard.title")}</p>
          <p className="text-xs text-muted">{t("panel.autoCard.subtitle")}</p>
        </div>
        <Badge tone={statusTone}>{statusText}</Badge>
        <div className="w-full sm:w-auto">
          <Toggle
            checked={draft.enabled}
            onChange={(enabled) => setDraft({ ...draft, enabled })}
            label={t("panel.autoCard.enabled")}
          />
        </div>
      </Card>

      <div className="grid gap-3 sm:grid-cols-3">
        <StatTile dense icon={Clock} label={t("panel.autoCard.pending")} value={formatNumber(data.stats.pending_invoices)} />
        <StatTile
          dense
          icon={CheckCircle2}
          tone="success"
          label={t("panel.autoCard.approvedToday")}
          value={formatNumber(data.stats.approved_today)}
        />
        <StatTile dense icon={Wallet} label={t("panel.autoCard.amountToday")} value={formatToman(data.stats.amount_today)} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <SectionCard title={t("panel.autoCard.card")} description={t("panel.autoCard.cardHint")}>
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <Input
                label={t("panel.autoCard.cardNumber")}
                ltr
                inputMode="numeric"
                value={draft.card_number}
                onChange={(e) => setDraft({ ...draft, card_number: e.target.value })}
              />
              <Input
                label={t("panel.autoCard.cardName")}
                value={draft.card_name}
                onChange={(e) => setDraft({ ...draft, card_name: e.target.value })}
              />
            </div>
            <div>
              <p className="mb-1.5 text-sm text-muted">{t("panel.autoCard.visibility")}</p>
              <SegmentedControl
                options={[
                  { value: "safe_mode", label: t("panel.autoCard.visibilitySafe") },
                  { value: "all", label: t("panel.autoCard.visibilityAll") },
                ]}
                value={draft.visibility}
                onChange={(visibility) => setDraft({ ...draft, visibility: visibility as PanelAutoCardVisibility })}
              />
              <p className="mt-1.5 text-xs text-muted">{t("panel.autoCard.visibilityHint")}</p>
            </div>
          </div>
        </SectionCard>

        <SectionCard title={t("panel.autoCard.rules")} description={t("panel.autoCard.rulesHint")}>
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <Input
                label={t("panel.autoCard.minAmount")}
                inputMode="numeric"
                value={draft.deposit_min}
                onChange={(e) => setDraft({ ...draft, deposit_min: digits(e.target.value) })}
              />
              <Input
                label={t("panel.autoCard.maxAmount")}
                inputMode="numeric"
                value={draft.deposit_max}
                onChange={(e) => setDraft({ ...draft, deposit_max: digits(e.target.value) })}
              />
            </div>
            <div className="flex flex-wrap items-end gap-3">
              <div className="flex-1">
                <Toggle
                  checked={draft.bonus_enabled}
                  onChange={(bonus_enabled) => setDraft({ ...draft, bonus_enabled })}
                  label={t("panel.autoCard.bonus")}
                  hint={t("panel.autoCard.bonusHint")}
                />
              </div>
              <div className="w-24">
                <Input
                  label="%"
                  inputMode="numeric"
                  value={draft.bonus_percent}
                  onChange={(e) => setDraft({ ...draft, bonus_percent: digits(e.target.value).slice(0, 3) })}
                />
              </div>
            </div>
          </div>
        </SectionCard>
      </div>

      <div className="flex justify-end">
        <Button loading={save.isPending} onClick={handleSave}>
          {t("panel.autoCard.save")}
        </Button>
      </div>

      <SectionCard title={t("panel.autoCard.webhook")} description={t("panel.autoCard.webhookHint")}>
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="space-y-3">
            {data.webhook_url ? (
              <CopyField label={t("panel.autoCard.webhookUrl")} value={data.webhook_url} />
            ) : (
              <p className="rounded-md border border-warning/30 bg-warning/10 p-2 text-xs text-warning">
                {t("panel.autoCard.noWebhook")}
              </p>
            )}
            {data.api_key ? (
              <CopyField
                label={t("panel.autoCard.apiKey")}
                value={data.api_key}
                display={showKey ? data.api_key : maskKey(data.api_key)}
              />
            ) : (
              <p className="rounded-md border border-warning/30 bg-warning/10 p-2 text-xs text-warning">
                {t("panel.autoCard.noKey")}
              </p>
            )}
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="secondary" disabled={!data.api_key} onClick={() => setShowKey((v) => !v)}>
                {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
                {showKey ? t("panel.autoCard.hideKey") : t("panel.autoCard.showKey")}
              </Button>
              <ConfirmButton
                size="sm"
                variant="danger"
                loading={rotate.isPending}
                message={t("panel.autoCard.rotateConfirm")}
                confirmLabel={t("panel.autoCard.rotateConfirmButton")}
                onConfirm={() => rotate.mutate({}, { onSuccess: () => setShowKey(true) })}
              >
                <RefreshCw size={14} />
                {t("panel.autoCard.rotate")}
              </ConfirmButton>
            </div>
            <p className="text-xs text-muted">{t("panel.autoCard.keyHint")}</p>
          </div>

          <div className="space-y-3 rounded-md border border-border bg-surface-2/40 p-3">
            <p className="text-sm font-semibold text-text">{t("panel.autoCard.guideTitle")}</p>
            <SegmentedControl
              options={[
                { value: "forapp", label: "ForApp" },
                { value: "smsforwarder", label: "SmsForwarder" },
              ]}
              value={app}
              onChange={(value) => setApp(value as Forwarder)}
            />
            <ol className="list-decimal space-y-1.5 ps-5 text-xs leading-6 text-muted">
              {Array.from({ length: GUIDE_STEPS[app] }, (_, index) => (
                <li key={`${app}-${index}`}>{t(`panel.autoCard.guide.${app}.step${index + 1}`)}</li>
              ))}
            </ol>
            {app === "smsforwarder" && (
              <CopyField label={t("panel.autoCard.guideTemplate")} value={SMS_FORWARDER_TEMPLATE} />
            )}
            <p className="rounded-md border border-border bg-surface-2 p-2 text-xs leading-6 text-muted">
              {t(`panel.autoCard.guide.${app}.note`)}
            </p>
          </div>
        </div>
      </SectionCard>
    </div>
  );
}
