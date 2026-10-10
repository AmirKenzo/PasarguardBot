import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { PageHeader } from "../../components/layout/PageHeader";
import { CheckCircle2, ExternalLink, FlaskConical, Loader2, Search } from "lucide-react";
import { Badge, Button, Card, Input } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";
import { useAuth } from "../../context/AuthContext";
import { useTelegram } from "../../hooks/useTelegram";
import { formatNumber, formatToman } from "../../lib/format";
import {
  useBalanceMethodsQuery,
  useCheckZarinpalMutation,
  useDepositZarinpalMutation,
  useOpenZarinpalPaymentQuery,
} from "../../queries/useBalance";
import type { ZarinpalPayment } from "../../types/webapp";

// Each check is a verify call to Zarinpal, so poll gently and also re-check when the buyer comes back.
const POLL_INTERVAL_MS = 15_000;

type BadgeTone = "primary" | "success" | "warning" | "danger" | "muted";

function statusTone(status: string): BadgeTone {
  if (status === "completed") return "success";
  if (status === "pending") return "warning";
  return "danger";
}

function parseAmount(value: string): number {
  return parseInt(value.replace(/,/g, ""), 10) || 0;
}

export default function ZarinpalDeposit() {
  const { t } = useTranslation();
  const { refreshUser } = useAuth();
  const { openLink, haptic } = useTelegram();
  const { show } = useToast();
  const { data: methods } = useBalanceMethodsQuery();
  const openQuery = useOpenZarinpalPaymentQuery(true);
  const deposit = useDepositZarinpalMutation();
  const check = useCheckZarinpalMutation();

  const [amount, setAmount] = useState("");
  const [payment, setPayment] = useState<ZarinpalPayment | null>(null);

  const min = methods?.zarinpal_deposit_min ?? 0;
  const max = methods?.zarinpal_deposit_max ?? 0;
  const isOpen = payment?.status === "pending";

  useEffect(() => {
    if (!payment && openQuery.data?.payment) setPayment(openQuery.data.payment);
  }, [openQuery.data, payment]);

  useEffect(() => {
    if (!payment || !isOpen) return;
    const tick = () => {
      if (!check.isPending) void refresh(payment.id, true);
    };
    const id = window.setInterval(tick, POLL_INTERVAL_MS);
    const onVisible = () => {
      if (document.visibilityState === "visible") tick();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVisible);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [payment?.id, isOpen]);

  function applyPayment(next: ZarinpalPayment | null | undefined) {
    if (!next) return;
    if (next.status === "completed" && payment?.status !== "completed") {
      haptic.notify("success");
      show(t("zarinpalDeposit.paidToast"), "success");
      void refreshUser();
    }
    setPayment(next);
  }

  async function refresh(id: number, silent = false) {
    try {
      const res = await check.mutateAsync(id);
      applyPayment(res.payment);
      if (!silent && res.payment && res.payment.status === "pending") {
        show(t("zarinpalDeposit.notPaidYet"), "info");
      }
    } catch (err) {
      if (!silent) show(err instanceof Error ? err.message : t("manualDeposit.genericError"), "error");
    }
  }

  async function handleCreate() {
    const value = parseAmount(amount);
    if (value < min || value > max) {
      show(t("manualDeposit.amountRangeError", { min: formatNumber(min), max: formatNumber(max) }), "error");
      return;
    }
    try {
      const res = await deposit.mutateAsync(value);
      applyPayment(res.payment);
      if (res.payment?.payment_url) openLink(res.payment.payment_url);
    } catch (err) {
      show(err instanceof Error ? err.message : t("manualDeposit.genericError"), "error");
    }
  }

  return (
    <div>
      <PageHeader title={t("zarinpalDeposit.title")} back="/balance" />

      {methods?.zarinpal_sandbox && (
        <div className="mb-4 flex items-start gap-2 rounded-xl border border-primary/30 bg-primary/10 p-3 text-xs leading-relaxed text-primary">
          <FlaskConical size={15} className="mt-0.5 shrink-0" />
          <p>{t("zarinpalDeposit.sandboxNote")}</p>
        </div>
      )}

      {payment ? (
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0">
              <p className="text-xs text-muted">{t("zarinpalDeposit.orderId")}</p>
              <p className="ltr-field truncate font-mono text-sm text-text" dir="ltr">
                {payment.order_id}
              </p>
            </div>
            <Badge tone={statusTone(payment.status)}>{payment.status_label}</Badge>
          </div>

          {payment.status === "completed" && (
            <Card className="flex items-center gap-3 border-success/30 bg-success/10 p-4">
              <CheckCircle2 size={28} className="shrink-0 text-success" />
              <div>
                <p className="font-semibold text-success">{t("zarinpalDeposit.paidTitle")}</p>
                {payment.ref_id && (
                  <p className="text-sm text-muted">
                    {t("zarinpalDeposit.refId")}:{" "}
                    <span className="ltr-field font-mono" dir="ltr">
                      {payment.ref_id}
                    </span>
                  </p>
                )}
              </div>
            </Card>
          )}

          <Card className="space-y-1 p-4">
            <p className="text-xs text-muted">{t("zarinpalDeposit.chargeAmount")}</p>
            <p className="text-2xl font-semibold text-text">{formatToman(payment.amount)}</p>
          </Card>

          {isOpen && (
            <>
              {payment.payment_url && (
                <Button fullWidth onClick={() => openLink(payment.payment_url!)}>
                  <ExternalLink size={15} />
                  {t("zarinpalDeposit.payButton")}
                </Button>
              )}
              <Button fullWidth variant="ghost" loading={check.isPending} onClick={() => void refresh(payment.id)}>
                <Search size={15} />
                {t("zarinpalDeposit.checkButton")}
              </Button>
              <p className="flex items-center justify-center gap-1.5 text-center text-xs text-muted">
                <Loader2 size={12} className="shrink-0 animate-spin" />
                {t("zarinpalDeposit.autoCheckNote")}
              </p>
            </>
          )}

          {!isOpen && (
            <Button fullWidth variant="secondary" onClick={() => setPayment(null)}>
              {t("zarinpalDeposit.newPayment")}
            </Button>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          <p className="text-sm text-muted">
            {t("manualDeposit.amountRange", { min: formatNumber(min), max: formatNumber(max) })}
            {methods?.zarinpal_bonus_percent
              ? t("manualDeposit.bonus", { percent: methods.zarinpal_bonus_percent })
              : ""}
          </p>
          <Input
            inputMode="numeric"
            placeholder={t("manualDeposit.amountPlaceholder")}
            value={amount}
            onChange={(e) => setAmount(e.target.value.replace(/\D/g, ""))}
          />
          <Button fullWidth loading={deposit.isPending} onClick={() => void handleCreate()}>
            {t("zarinpalDeposit.submitButton")}
          </Button>
        </div>
      )}
    </div>
  );
}
