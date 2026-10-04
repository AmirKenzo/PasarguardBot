import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Copy, Gem, PlugZap, XCircle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Card, ErrorState, Input, Skeleton } from "../../components/ui";
import { SegmentedControl } from "../../components/ui/Select";
import { useToast } from "../../components/ui/Toast";
import { panelPaymentsApi } from "../../api/panel";
import { copyToClipboard, formatNumber } from "../../lib/format";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import type { PanelTonPaysMode, PanelTonPaysResponse } from "../../types/panel";
import { SectionCard, Toggle } from "./components";

const QUERY_KEY = ["tonpays"];

interface Draft {
  enabled: boolean;
  mode: PanelTonPaysMode;
  api_key: string;
  custom_key: string;
  deposit_min: string;
  deposit_max: string;
  bonus_enabled: boolean;
  bonus_percent: string;
}

function toDraft(data: PanelTonPaysResponse): Draft {
  return {
    enabled: data.enabled,
    mode: data.mode,
    api_key: "",
    custom_key: "",
    deposit_min: String(data.deposit_min),
    deposit_max: String(data.deposit_max),
    bonus_enabled: data.bonus_enabled,
    bonus_percent: String(data.bonus_percent),
  };
}

function digits(value: string): string {
  return value.replace(/\D/g, "");
}

export default function TonPaysTab() {
  const { t } = useTranslation();
  const { show } = useToast();
  const query = usePanelQuery(QUERY_KEY, (auth) => panelPaymentsApi.getTonPays(auth));
  const save = usePanelAction(panelPaymentsApi.saveTonPays, { invalidate: [QUERY_KEY] });
  const test = usePanelAction(panelPaymentsApi.testTonPays);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [testResult, setTestResult] = useState<{ ok: boolean; text: string } | null>(null);

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
  const activeKeySet = draft.mode === "custom" ? data.has_custom_key || !!draft.custom_key : data.has_api_key || !!draft.api_key;

  const handleSave = () => {
    const min = Number(digits(draft.deposit_min)) || 0;
    const max = Number(digits(draft.deposit_max)) || 0;
    if (max < min) {
      show(t("panel.tonpays.rangeError"), "error");
      return;
    }
    save.mutate({
      enabled: draft.enabled,
      mode: draft.mode,
      api_key: draft.api_key.trim(),
      custom_key: draft.custom_key.trim(),
      deposit_min: min,
      deposit_max: max,
      bonus_enabled: draft.bonus_enabled,
      bonus_percent: Math.min(100, Number(digits(draft.bonus_percent)) || 0),
    });
  };

  const handleTest = async () => {
    setTestResult(null);
    const typed = draft.mode === "custom" ? draft.custom_key : draft.api_key;
    try {
      const res = await test.mutateAsync({ mode: draft.mode, api_key: typed.trim() });
      setTestResult({ ok: true, text: res.message || t("panel.tonpays.connected") });
    } catch (err) {
      setTestResult({ ok: false, text: err instanceof Error ? err.message : t("panel.tonpays.notConnected") });
    }
  };

  const statusTone = data.ready ? "success" : data.enabled ? "warning" : "muted";
  const statusText = data.ready
    ? t("panel.tonpays.statusActive")
    : data.enabled
      ? t("panel.tonpays.statusNoKey")
      : t("panel.tonpays.statusOff");

  return (
    <div className="space-y-4">
      <Card className="flex flex-wrap items-center gap-3 p-4">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <Gem size={22} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-text">{t("panel.tonpays.title")}</p>
          <p className="text-xs text-muted">
            {data.mode === "custom" ? t("panel.tonpays.modeCustom") : t("panel.tonpays.modeStandard")}
            {" · "}
            {activeKeySet ? t("panel.tonpays.keySet") : t("panel.tonpays.keyMissing")}
          </p>
        </div>
        <Badge tone={statusTone}>{statusText}</Badge>
        <div className="w-full sm:w-auto">
          <Toggle
            checked={draft.enabled}
            onChange={(enabled) => setDraft({ ...draft, enabled })}
            label={t("panel.tonpays.enabled")}
          />
        </div>
      </Card>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label={t("panel.tonpays.paidToday")} value={formatNumber(data.stats.paid_today)} />
        <Stat label={t("panel.tonpays.amountToday")} value={formatNumber(data.stats.amount_today)} suffix={t("common.toman")} />
        <Stat label={t("panel.tonpays.openInvoices")} value={formatNumber(data.stats.open_invoices)} />
        <Stat label={t("panel.tonpays.failedToday")} value={formatNumber(data.stats.failed_today)} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <SectionCard title={t("panel.tonpays.connection")} description={t("panel.tonpays.connectionHint")}>
          <div className="space-y-4">
            <div>
              <p className="mb-1.5 text-sm text-muted">{t("panel.tonpays.gatewayType")}</p>
              <SegmentedControl
                options={[
                  { value: "standard", label: t("panel.tonpays.standard") },
                  { value: "custom", label: t("panel.tonpays.custom") },
                ]}
                value={draft.mode}
                onChange={(mode) => {
                  setDraft({ ...draft, mode: mode as PanelTonPaysMode });
                  setTestResult(null);
                }}
              />
              <p className="mt-1.5 text-xs text-muted">
                {draft.mode === "custom" ? t("panel.tonpays.customHint") : t("panel.tonpays.standardHint")}
              </p>
            </div>
            <KeyField
              label={t("panel.tonpays.apiKey")}
              masked={data.api_key_masked}
              value={draft.api_key}
              active={draft.mode === "standard"}
              onChange={(api_key) => setDraft({ ...draft, api_key })}
            />
            <KeyField
              label={t("panel.tonpays.customKey")}
              masked={data.custom_key_masked}
              value={draft.custom_key}
              active={draft.mode === "custom"}
              onChange={(custom_key) => setDraft({ ...draft, custom_key })}
            />
            <div className="flex flex-wrap items-center gap-3">
              <Button variant="secondary" size="sm" loading={test.isPending} onClick={() => void handleTest()}>
                <PlugZap size={15} />
                {t("panel.tonpays.testConnection")}
              </Button>
              {testResult && (
                <span className={`flex items-center gap-1 text-xs ${testResult.ok ? "text-success" : "text-danger"}`}>
                  {testResult.ok ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
                  {testResult.text}
                </span>
              )}
            </div>
          </div>
        </SectionCard>

        <SectionCard title={t("panel.tonpays.rules")} description={t("panel.tonpays.rulesHint")}>
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <Input
                label={t("panel.tonpays.minAmount")}
                inputMode="numeric"
                value={draft.deposit_min}
                onChange={(e) => setDraft({ ...draft, deposit_min: digits(e.target.value) })}
              />
              <Input
                label={t("panel.tonpays.maxAmount")}
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
                  label={t("panel.tonpays.bonus")}
                  hint={t("panel.tonpays.bonusHint")}
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
            <div>
              <p className="mb-1.5 text-sm text-muted">{t("panel.tonpays.webhook")}</p>
              {data.webhook_url ? (
                <div className="flex items-center gap-2 rounded-md border border-border bg-surface-2 px-3 py-2">
                  <code className="ltr-field min-w-0 flex-1 break-all text-[11px] text-primary" dir="ltr">
                    {data.webhook_url}
                  </code>
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-label={t("panel.tonpays.copy")}
                    onClick={() => void copyToClipboard(data.webhook_url!).then(() => show(t("panel.tonpays.copied"), "success"))}
                  >
                    <Copy size={14} />
                  </Button>
                </div>
              ) : (
                <p className="rounded-md border border-warning/30 bg-warning/10 p-2 text-xs text-warning">
                  {t("panel.tonpays.noWebhook")}
                </p>
              )}
              <p className="mt-1.5 text-xs text-muted">{t("panel.tonpays.webhookHint")}</p>
            </div>
          </div>
        </SectionCard>
      </div>

      <div className="flex items-start gap-2 rounded-md border border-danger/30 bg-danger/10 p-3">
        <AlertTriangle size={15} className="mt-0.5 shrink-0 text-danger" />
        <p className="text-xs font-semibold leading-relaxed text-danger">{t("panel.settings.tonpaysDisclaimer")}</p>
      </div>

      <div className="flex justify-end">
        <Button loading={save.isPending} onClick={handleSave}>
          {t("panel.tonpays.save")}
        </Button>
      </div>
    </div>
  );
}

function Stat({ label, value, suffix }: { label: string; value: string; suffix?: string }) {
  return (
    <Card className="p-3">
      <p className="text-xs text-muted">{label}</p>
      <p className="mt-1 text-lg font-semibold text-text">
        {value}
        {suffix && <span className="ms-1 text-xs font-normal text-muted">{suffix}</span>}
      </p>
    </Card>
  );
}

function KeyField({
  label,
  masked,
  value,
  active,
  onChange,
}: {
  label: string;
  masked: string;
  value: string;
  active: boolean;
  onChange: (value: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <div className={active ? "" : "opacity-60"}>
      <Input
        label={label}
        ltr
        autoComplete="off"
        placeholder={masked || t("panel.tonpays.keyPlaceholder")}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      <p className="mt-1 text-xs text-muted">
        {masked ? t("panel.tonpays.keyKeepHint", { masked }) : t("panel.tonpays.keyEmptyHint")}
      </p>
    </div>
  );
}
