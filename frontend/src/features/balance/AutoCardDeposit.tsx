import { useEffect, useState } from "react";
import { CheckCircle2, Clock, Copy, Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button, Card, IconBadge, Input } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";
import { copyToClipboard, formatNumber } from "../../lib/format";
import { useAutoCardStatusQuery, useBalanceMethodsQuery, useDepositAutoCardMutation } from "../../queries/useBalance";

function parseAmount(value: string): number {
  return parseInt(value.replace(/,/g, ""), 10) || 0;
}

/** Re-render once a second so the countdown and the expiry switch stay live. */
function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [active]);
  return now;
}

function formatCountdown(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

export default function AutoCardDeposit() {
  const { t } = useTranslation();
  const { data: methods } = useBalanceMethodsQuery();
  const deposit = useDepositAutoCardMutation();
  const { show } = useToast();
  const [amount, setAmount] = useState("");

  const result = deposit.data;
  const min = methods?.auto_deposit_min ?? 0;
  const max = methods?.auto_deposit_max ?? 0;
  const statusQuery = useAutoCardStatusQuery(
    result?.ok && result.order_id != null && result.amount_irt != null && result.created_at != null
      ? { orderId: result.order_id, amountIrt: result.amount_irt, createdAt: result.created_at }
      : null
  );
  const paid = statusQuery.data?.status === "paid";
  const invoiceActive = !!result?.ok && !paid;
  const now = useNow(invoiceActive);
  const expiresAtMs = result?.expires_at ? result.expires_at * 1000 : null;
  const expired = (expiresAtMs != null && now >= expiresAtMs) || statusQuery.data?.status === "expired";

  async function handleSubmit() {
    const value = parseAmount(amount);
    if (value < min || value > max) {
      show(t("manualDeposit.amountRangeError", { min: formatNumber(min), max: formatNumber(max) }), "error");
      return;
    }
    try {
      const res = await deposit.mutateAsync(value);
      if (!res.ok) show(res.error ?? t("manualDeposit.genericError"), "error");
    } catch (err) {
      show(err instanceof Error ? err.message : t("manualDeposit.genericError"), "error");
    }
  }

  async function handleCopy(value: string) {
    try {
      await copyToClipboard(value);
      show(t("common.copied"), "success");
    } catch {
      show(t("common.copyFailed"), "error");
    }
  }

  // The last 3 digits are the SMS-matching cue, so they're highlighted separately —
  // formatNumber's thousands grouping means the final 3 characters are always exactly
  // the ones/tens/hundreds digits, whatever locale digit set is in use.
  const rialFormatted = result?.amount_rial != null ? formatNumber(result.amount_rial) : "";
  const rialHead = rialFormatted.slice(0, -3);
  const rialTail = rialFormatted.slice(-3) || rialFormatted;

  return (
    <div>
      <PageHeader
        title={t("autoCardDeposit.title")}
        subtitle={
          invoiceActive && result?.order_id != null
            ? t("autoCardDeposit.invoiceSubtitle", { id: result.order_id })
            : undefined
        }
        back="/balance"
      />

      {result?.ok && paid ? (
        <Card className="flex items-center gap-3 border-success/30 bg-success/10 p-4">
          <CheckCircle2 size={28} className="shrink-0 text-success" />
          <div>
            <p className="font-semibold text-success">{t("autoCardDeposit.paidTitle")}</p>
            <p className="text-sm text-muted">{t("autoCardDeposit.paidDesc")}</p>
          </div>
        </Card>
      ) : result?.ok && expired ? (
        <Card className="flex flex-col items-center gap-3 p-6 text-center">
          <IconBadge icon={Clock} tone="danger" size="lg" />
          <p className="font-bold text-text">{t("autoCardDeposit.expiredTitle")}</p>
          <p className="text-sm leading-6 text-muted">{t("autoCardDeposit.expiredDesc")}</p>
          <Button fullWidth className="mt-1" onClick={() => deposit.reset()}>
            {t("autoCardDeposit.newInvoice")}
          </Button>
        </Card>
      ) : result?.ok ? (
        <div className="space-y-4">
          {result.amount_rial != null && (
            <Card className="flex flex-col items-center gap-2.5 p-5 text-center">
              <p className="text-xs font-semibold text-muted">{t("autoCardDeposit.exactAmountLabel")}</p>
              <p className="ltr-field font-mono text-3xl font-extrabold tracking-tight text-text" dir="ltr">
                {rialHead}
                <mark className="rounded-sm bg-warning/20 px-1 text-warning">{rialTail}</mark>
              </p>
              <p className="text-xs leading-6 text-muted">
                {t("autoCardDeposit.exactAmountHint", { digits: rialTail })}
              </p>
              <Button variant="secondary" size="sm" onClick={() => void handleCopy(String(result.amount_rial))}>
                <Copy size={14} />
                {t("autoCardDeposit.copyRialAmount")}
              </Button>
            </Card>
          )}

          {result.card_number && (
            <Card className="p-4">
              <p className="text-sm text-muted">{t("manualDeposit.cardNumber")}</p>
              <p className="ltr-field break-all font-mono text-text" dir="ltr">
                {result.card_number}
              </p>
              {result.card_name && (
                <p className="mt-2 text-sm text-muted">
                  {t("manualDeposit.cardHolder")}: {result.card_name}
                </p>
              )}
              <Button
                variant="secondary"
                size="sm"
                className="mt-2"
                onClick={() => void handleCopy(result.card_number!)}
              >
                {t("manualDeposit.copyCardNumber")}
              </Button>
            </Card>
          )}

          {expiresAtMs != null && (
            <p className="flex items-center justify-center gap-1.5 text-center text-xs text-muted">
              <Clock size={12} className="shrink-0" />
              {t("autoCardDeposit.timeLeft", { time: formatCountdown(expiresAtMs - now) })}
            </p>
          )}
          <p className="flex items-center justify-center gap-1.5 text-center text-xs text-muted">
            <Loader2 size={12} className="shrink-0 animate-spin" />
            {t("autoCardDeposit.waitingForSms")}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          <p className="text-sm text-muted">
            {t("manualDeposit.amountRange", { min: formatNumber(min), max: formatNumber(max) })}
            {methods?.auto_bonus_percent ? t("manualDeposit.bonus", { percent: methods.auto_bonus_percent }) : ""}
          </p>
          <Input
            inputMode="numeric"
            placeholder={t("manualDeposit.amountPlaceholder")}
            value={amount}
            onChange={(e) => setAmount(e.target.value.replace(/\D/g, ""))}
          />
          <Button fullWidth loading={deposit.isPending} onClick={() => void handleSubmit()}>
            {t("autoCardDeposit.createInvoice")}
          </Button>
        </div>
      )}
    </div>
  );
}
