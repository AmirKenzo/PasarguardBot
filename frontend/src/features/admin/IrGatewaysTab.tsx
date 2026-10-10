import { useEffect, useState } from "react";
import { CheckCircle2, Copy, FlaskConical, PlugZap, XCircle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Card, ErrorState, Input, Skeleton } from "../../components/ui";
import { SegmentedControl } from "../../components/ui/Select";
import { useToast } from "../../components/ui/Toast";
import { panelPaymentsApi } from "../../api/panel";
import { irGatewayIcon } from "../../lib/irGateways";
import { copyToClipboard, formatNumber } from "../../lib/format";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import type { PanelIrGatewayRow } from "../../types/panel";
import { SectionCard, Toggle } from "./components";

const QUERY_KEY = ["ir-gateways"];

interface Draft {
  enabled: boolean;
  sandbox: boolean;
  merchant_id: string;
  deposit_min: string;
  deposit_max: string;
  bonus_enabled: boolean;
  bonus_percent: string;
}

function toDraft(row: PanelIrGatewayRow): Draft {
  return {
    enabled: row.enabled,
    sandbox: row.sandbox,
    merchant_id: "",
    deposit_min: String(row.deposit_min),
    deposit_max: String(row.deposit_max),
    bonus_enabled: row.bonus_enabled,
    bonus_percent: String(row.bonus_percent),
  };
}

function digits(value: string): string {
  return value.replace(/\D/g, "");
}

/** Python's `re` pattern for the merchant, as sent by the backend; null when JS cannot compile it. */
function merchantRegex(pattern: string): RegExp | null {
  try {
    return pattern ? new RegExp(pattern) : null;
  } catch {
    return null;
  }
}

export default function IrGatewaysTab() {
  const { t } = useTranslation();
  const query = usePanelQuery(QUERY_KEY, (auth) => panelPaymentsApi.getIrGateways(auth));

  if (query.isError) {
    return <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />;
  }
  if (query.isLoading || !query.data) {
    return <Skeleton className="h-96 w-full" />;
  }
  return (
    <div className="space-y-8">
      <p className="text-sm text-muted">{t("panel.irGateways.intro")}</p>
      {query.data.gateways.map((row) => (
        <GatewayCard key={row.key} row={row} />
      ))}
    </div>
  );
}

function GatewayCard({ row }: { row: PanelIrGatewayRow }) {
  const { t } = useTranslation();
  const { show } = useToast();
  const save = usePanelAction(panelPaymentsApi.saveIrGateway, { invalidate: [QUERY_KEY] });
  const test = usePanelAction(panelPaymentsApi.testIrGateway);
  const [draft, setDraft] = useState<Draft>(() => toDraft(row));
  const [testResult, setTestResult] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => setDraft(toDraft(row)), [row]);

  const Icon = irGatewayIcon(row.key);
  const typedMerchant = draft.merchant_id.trim();
  const pattern = merchantRegex(row.merchant_pattern);
  const merchantInvalid = typedMerchant !== "" && !!pattern && !pattern.test(typedMerchant);

  const handleSave = () => {
    const min = Number(digits(draft.deposit_min)) || 0;
    const max = Number(digits(draft.deposit_max)) || 0;
    if (max < min) {
      show(t("panel.irGateways.rangeError"), "error");
      return;
    }
    if (merchantInvalid) {
      show(row.merchant_hint, "error");
      return;
    }
    save.mutate({
      gateway: row.key,
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
      setTestResult({ ok: false, text: row.merchant_hint });
      return;
    }
    try {
      const res = await test.mutateAsync({ gateway: row.key, sandbox: draft.sandbox, merchant_id: typedMerchant });
      setTestResult({ ok: true, text: res.message || t("panel.irGateways.connected") });
    } catch (err) {
      setTestResult({ ok: false, text: err instanceof Error ? err.message : t("panel.irGateways.notConnected") });
    }
  };

  const statusTone = row.ready ? (row.sandbox ? "primary" : "success") : row.enabled ? "warning" : "muted";
  const statusText = row.ready
    ? row.sandbox
      ? t("panel.irGateways.statusSandbox")
      : t("panel.irGateways.statusActive")
    : row.enabled
      ? t("panel.irGateways.statusNotReady")
      : t("panel.irGateways.statusOff");

  return (
    <section className="space-y-4">
      <Card className="flex flex-wrap items-center gap-3 p-4">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <Icon size={22} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-text">{row.title}</p>
          <p className="text-xs text-muted">
            {row.sandbox ? t("panel.irGateways.modeSandbox") : t("panel.irGateways.modeLive")}
            {" · "}
            {row.has_merchant ? t("panel.irGateways.merchantSet") : t("panel.irGateways.merchantMissing")}
          </p>
        </div>
        <Badge tone={statusTone}>{statusText}</Badge>
        <div className="w-full sm:w-auto">
          <Toggle
            checked={draft.enabled}
            onChange={(enabled) => setDraft({ ...draft, enabled })}
            label={t("panel.irGateways.enabled")}
          />
        </div>
      </Card>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label={t("panel.tonpays.paidToday")} value={formatNumber(row.stats.paid_today)} />
        <Stat
          label={t("panel.tonpays.amountToday")}
          value={formatNumber(row.stats.amount_today)}
          suffix={t("common.toman")}
        />
        <Stat label={t("panel.irGateways.openPayments")} value={formatNumber(row.stats.open_payments)} />
        <Stat label={t("panel.tonpays.failedToday")} value={formatNumber(row.stats.failed_today)} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <SectionCard title={t("panel.irGateways.connection")} description={t("panel.irGateways.connectionHint")}>
          <div className="space-y-4">
            <div>
              <p className="mb-1.5 text-sm text-muted">{t("panel.irGateways.mode")}</p>
              <SegmentedControl
                options={[
                  { value: "sandbox", label: t("panel.irGateways.sandbox") },
                  { value: "live", label: t("panel.irGateways.live") },
                ]}
                value={draft.sandbox ? "sandbox" : "live"}
                onChange={(mode) => {
                  setDraft({ ...draft, sandbox: mode === "sandbox" });
                  setTestResult(null);
                }}
              />
              <p className="mt-1.5 text-xs text-muted">
                {draft.sandbox ? row.sandbox_hint : t("panel.irGateways.liveHint")}
              </p>
            </div>
            <div>
              <Input
                label={t("panel.irGateways.merchantId")}
                ltr
                autoComplete="off"
                placeholder={row.merchant_masked || "merchant"}
                value={draft.merchant_id}
                onChange={(e) => setDraft({ ...draft, merchant_id: e.target.value })}
              />
              <p className={`mt-1 text-xs ${merchantInvalid ? "text-danger" : "text-muted"}`}>
                {merchantInvalid
                  ? row.merchant_hint
                  : row.merchant_masked
                    ? t("panel.tonpays.keyKeepHint", { masked: row.merchant_masked })
                    : row.merchant_hint}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Button variant="secondary" size="sm" loading={test.isPending} onClick={() => void handleTest()}>
                <PlugZap size={15} />
                {t("panel.irGateways.testConnection")}
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
              <p className="mb-1.5 text-sm text-muted">{t("panel.irGateways.callback")}</p>
              {row.callback_url ? (
                <div className="flex items-center gap-2 rounded-md border border-border bg-surface-2 px-3 py-2">
                  <code className="ltr-field min-w-0 flex-1 break-all text-[11px] text-primary" dir="ltr">
                    {row.callback_url}
                  </code>
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-label={t("panel.tonpays.copy")}
                    onClick={() =>
                      void copyToClipboard(row.callback_url!).then(() => show(t("panel.tonpays.copied"), "success"))
                    }
                  >
                    <Copy size={14} />
                  </Button>
                </div>
              ) : (
                <p className="rounded-md border border-warning/30 bg-warning/10 p-2 text-xs text-warning">
                  {t("panel.irGateways.noCallback")}
                </p>
              )}
              <p className="mt-1.5 text-xs text-muted">{t("panel.irGateways.callbackHint")}</p>
            </div>
          </div>
        </SectionCard>
      </div>

      {draft.sandbox && (
        <div className="flex items-start gap-2 rounded-md border border-primary/30 bg-primary/10 p-3">
          <FlaskConical size={15} className="mt-0.5 shrink-0 text-primary" />
          <p className="text-xs leading-relaxed text-primary">{t("panel.irGateways.sandboxNote")}</p>
        </div>
      )}

      <div className="flex justify-end">
        <Button loading={save.isPending} onClick={handleSave}>
          {t("panel.irGateways.save", { name: row.title })}
        </Button>
      </div>
    </section>
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
