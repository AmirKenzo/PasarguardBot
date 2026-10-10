import { useEffect, useState } from "react";
import { CheckCircle2, Copy, FlaskConical, Landmark, PlugZap, XCircle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Card, ErrorState, Input, Skeleton } from "../../components/ui";
import { SegmentedControl } from "../../components/ui/Select";
import { useToast } from "../../components/ui/Toast";
import { panelPaymentsApi } from "../../api/panel";
import { copyToClipboard, formatNumber } from "../../lib/format";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import type { PanelZarinpalResponse } from "../../types/panel";
import { SectionCard, Toggle } from "./components";

const QUERY_KEY = ["zarinpal"];
const MERCHANT_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

interface Draft {
  enabled: boolean;
  sandbox: boolean;
  merchant_id: string;
  deposit_min: string;
  deposit_max: string;
  bonus_enabled: boolean;
  bonus_percent: string;
}

function toDraft(data: PanelZarinpalResponse): Draft {
  return {
    enabled: data.enabled,
    sandbox: data.sandbox,
    merchant_id: "",
    deposit_min: String(data.deposit_min),
    deposit_max: String(data.deposit_max),
    bonus_enabled: data.bonus_enabled,
    bonus_percent: String(data.bonus_percent),
  };
}

function digits(value: string): string {
  return value.replace(/\D/g, "");
}

export default function ZarinpalTab() {
  const { t } = useTranslation();
  const { show } = useToast();
  const query = usePanelQuery(QUERY_KEY, (auth) => panelPaymentsApi.getZarinpal(auth));
  const save = usePanelAction(panelPaymentsApi.saveZarinpal, { invalidate: [QUERY_KEY] });
  const test = usePanelAction(panelPaymentsApi.testZarinpal);
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
  const typedMerchant = draft.merchant_id.trim();
  const merchantInvalid = typedMerchant !== "" && !MERCHANT_PATTERN.test(typedMerchant);

  const handleSave = () => {
    const min = Number(digits(draft.deposit_min)) || 0;
    const max = Number(digits(draft.deposit_max)) || 0;
    if (max < min) {
      show(t("panel.zarinpal.rangeError"), "error");
      return;
    }
    if (merchantInvalid) {
      show(t("panel.zarinpal.merchantInvalid"), "error");
      return;
    }
    save.mutate({
      enabled: draft.enabled,
      sandbox: draft.sandbox,
      merchant_id: typedMerchant,
      deposit_min: min,
      deposit_max: max,
      bonus_enabled: draft.bonus_enabled,
      bonus_percent: Math.min(100, Number(digits(draft.bonus_percent)) || 0),
    });
  };

  const handleTest = async () => {
    setTestResult(null);
    if (merchantInvalid) {
      setTestResult({ ok: false, text: t("panel.zarinpal.merchantInvalid") });
      return;
    }
    try {
      const res = await test.mutateAsync({ sandbox: draft.sandbox, merchant_id: typedMerchant });
      setTestResult({ ok: true, text: res.message || t("panel.zarinpal.connected") });
    } catch (err) {
      setTestResult({ ok: false, text: err instanceof Error ? err.message : t("panel.zarinpal.notConnected") });
    }
  };

  const statusTone = data.ready ? (data.sandbox ? "primary" : "success") : data.enabled ? "warning" : "muted";
  const statusText = data.ready
    ? data.sandbox
      ? t("panel.zarinpal.statusSandbox")
      : t("panel.zarinpal.statusActive")
    : data.enabled
      ? t("panel.zarinpal.statusNotReady")
      : t("panel.zarinpal.statusOff");

  return (
    <div className="space-y-4">
      <Card className="flex flex-wrap items-center gap-3 p-4">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <Landmark size={22} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-text">{t("panel.zarinpal.title")}</p>
          <p className="text-xs text-muted">
            {data.sandbox ? t("panel.zarinpal.modeSandbox") : t("panel.zarinpal.modeLive")}
            {" · "}
            {data.has_merchant ? t("panel.zarinpal.merchantSet") : t("panel.zarinpal.merchantMissing")}
          </p>
        </div>
        <Badge tone={statusTone}>{statusText}</Badge>
        <div className="w-full sm:w-auto">
          <Toggle
            checked={draft.enabled}
            onChange={(enabled) => setDraft({ ...draft, enabled })}
            label={t("panel.zarinpal.enabled")}
          />
        </div>
      </Card>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label={t("panel.tonpays.paidToday")} value={formatNumber(data.stats.paid_today)} />
        <Stat
          label={t("panel.tonpays.amountToday")}
          value={formatNumber(data.stats.amount_today)}
          suffix={t("common.toman")}
        />
        <Stat label={t("panel.zarinpal.openPayments")} value={formatNumber(data.stats.open_invoices)} />
        <Stat label={t("panel.tonpays.failedToday")} value={formatNumber(data.stats.failed_today)} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <SectionCard title={t("panel.zarinpal.connection")} description={t("panel.zarinpal.connectionHint")}>
          <div className="space-y-4">
            <div>
              <p className="mb-1.5 text-sm text-muted">{t("panel.zarinpal.mode")}</p>
              <SegmentedControl
                options={[
                  { value: "sandbox", label: t("panel.zarinpal.sandbox") },
                  { value: "live", label: t("panel.zarinpal.live") },
                ]}
                value={draft.sandbox ? "sandbox" : "live"}
                onChange={(mode) => {
                  setDraft({ ...draft, sandbox: mode === "sandbox" });
                  setTestResult(null);
                }}
              />
              <p className="mt-1.5 text-xs text-muted">
                {draft.sandbox ? t("panel.zarinpal.sandboxHint") : t("panel.zarinpal.liveHint")}
              </p>
            </div>
            <div>
              <Input
                label={t("panel.zarinpal.merchantId")}
                ltr
                autoComplete="off"
                placeholder={data.merchant_masked || "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"}
                value={draft.merchant_id}
                onChange={(e) => setDraft({ ...draft, merchant_id: e.target.value })}
              />
              <p className={`mt-1 text-xs ${merchantInvalid ? "text-danger" : "text-muted"}`}>
                {merchantInvalid
                  ? t("panel.zarinpal.merchantInvalid")
                  : data.merchant_masked
                    ? t("panel.tonpays.keyKeepHint", { masked: data.merchant_masked })
                    : t("panel.zarinpal.merchantEmptyHint")}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Button variant="secondary" size="sm" loading={test.isPending} onClick={() => void handleTest()}>
                <PlugZap size={15} />
                {t("panel.zarinpal.testConnection")}
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
              <p className="mb-1.5 text-sm text-muted">{t("panel.zarinpal.callback")}</p>
              {data.callback_url ? (
                <div className="flex items-center gap-2 rounded-md border border-border bg-surface-2 px-3 py-2">
                  <code className="ltr-field min-w-0 flex-1 break-all text-[11px] text-primary" dir="ltr">
                    {data.callback_url}
                  </code>
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-label={t("panel.tonpays.copy")}
                    onClick={() =>
                      void copyToClipboard(data.callback_url!).then(() => show(t("panel.tonpays.copied"), "success"))
                    }
                  >
                    <Copy size={14} />
                  </Button>
                </div>
              ) : (
                <p className="rounded-md border border-warning/30 bg-warning/10 p-2 text-xs text-warning">
                  {t("panel.zarinpal.noCallback")}
                </p>
              )}
              <p className="mt-1.5 text-xs text-muted">{t("panel.zarinpal.callbackHint")}</p>
            </div>
          </div>
        </SectionCard>
      </div>

      {draft.sandbox && (
        <div className="flex items-start gap-2 rounded-md border border-primary/30 bg-primary/10 p-3">
          <FlaskConical size={15} className="mt-0.5 shrink-0 text-primary" />
          <p className="text-xs leading-relaxed text-primary">{t("panel.zarinpal.sandboxNote")}</p>
        </div>
      )}

      <div className="flex justify-end">
        <Button loading={save.isPending} onClick={handleSave}>
          {t("panel.zarinpal.save")}
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
