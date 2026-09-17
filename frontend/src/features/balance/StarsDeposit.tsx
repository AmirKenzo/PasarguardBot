import { useState } from "react";
import { useTranslation } from "react-i18next";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button, Card, Input } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";
import { useAuth } from "../../context/AuthContext";
import { useTelegram } from "../../hooks/useTelegram";
import { formatNumber, formatToman } from "../../lib/format";
import { useBalanceMethodsQuery, useDepositStarsMutation } from "../../queries/useBalance";

function parseAmount(value: string): number {
  return parseInt(value.replace(/,/g, ""), 10) || 0;
}

export default function StarsDeposit() {
  const { t } = useTranslation();
  const { refreshUser, initData } = useAuth();
  const { webApp, haptic } = useTelegram();
  const { data: methods } = useBalanceMethodsQuery();
  const deposit = useDepositStarsMutation();
  const { show } = useToast();
  const [amount, setAmount] = useState("");
  const [paid, setPaid] = useState(false);

  const result = deposit.data;
  const min = methods?.crypto_deposit_min ?? 0;
  const max = methods?.crypto_deposit_max ?? 0;
  const insideTelegram = !!initData && !!webApp?.openInvoice;

  async function openInvoice(url: string) {
    if (!webApp?.openInvoice) {
      show(t("starsDeposit.onlyInTelegramAlert"), "error");
      return;
    }
    webApp.openInvoice(url, (status) => {
      if (status === "paid") {
        setPaid(true);
        haptic.notify("success");
        show(t("starsDeposit.paymentSuccess"), "success");
        void refreshUser();
      } else if (status === "cancelled") {
        show(t("starsDeposit.paymentCancelled"), "info");
      } else if (status === "failed") {
        haptic.notify("error");
        show(t("starsDeposit.paymentFailed"), "error");
      }
    });
  }

  async function handleSubmit() {
    if (!insideTelegram) {
      show(t("starsDeposit.onlyInTelegramSubmit"), "error");
      return;
    }
    const value = parseAmount(amount);
    if (value < min || value > max) {
      show(t("manualDeposit.amountRangeError", { min: formatNumber(min), max: formatNumber(max) }), "error");
      return;
    }
    try {
      const res = await deposit.mutateAsync(value);
      if (res.invoice_url) await openInvoice(res.invoice_url);
    } catch (err) {
      show(err instanceof Error ? err.message : t("manualDeposit.genericError"), "error");
    }
  }

  return (
    <div>
      <PageHeader title={t("starsDeposit.title")} back="/balance" />

      {paid ? (
        <Card className="space-y-2 p-5">
          <p className="font-medium text-success">{t("starsDeposit.paidTitle")}</p>
          <p className="text-sm text-muted">{t("starsDeposit.paidDesc")}</p>
        </Card>
      ) : result?.invoice_url ? (
        <Card className="space-y-4 p-5">
          <p className="font-medium text-success">{result.message ?? t("starsDeposit.title")}</p>
          <div className="space-y-1 text-sm text-muted">
            {result.invoice_no && (
              <p>
                {t("cryptoDeposit.invoiceNumber")}:{" "}
                <span className="ltr-field font-mono text-text" dir="ltr">
                  {result.invoice_no}
                </span>
              </p>
            )}
            {result.amount_irt != null && (
              <p>
                {t("starsDeposit.amountLabel")}: {formatToman(result.amount_irt)}
              </p>
            )}
            {result.stars != null && (
              <p>
                {t("starsDeposit.starsLabel")}:{" "}
                <span className="ltr-field font-mono text-text" dir="ltr">
                  {formatNumber(result.stars)}
                </span>
              </p>
            )}
            {result.usd_rate_irt != null && (
              <p>
                {t("starsDeposit.usdRate")}: {formatToman(result.usd_rate_irt)}
              </p>
            )}
            {result.star_price_irt != null && (
              <p>
                {t("starsDeposit.starPrice")}: {formatToman(result.star_price_irt)}
              </p>
            )}
          </div>
          <Button fullWidth onClick={() => void openInvoice(result.invoice_url!)}>
            {t("starsDeposit.openInvoice")}
          </Button>
        </Card>
      ) : (
        <div className="space-y-4">
          {!insideTelegram && (
            <Card className="p-4 text-sm text-warning">{t("starsDeposit.onlyInTelegramNotice")}</Card>
          )}
          <p className="text-sm text-muted">
            {t("manualDeposit.amountRange", { min: formatNumber(min), max: formatNumber(max) })}
            {methods?.stars_bonus_percent ? t("manualDeposit.bonus", { percent: methods.stars_bonus_percent }) : ""}
          </p>
          <Input
            inputMode="numeric"
            placeholder={t("manualDeposit.amountPlaceholder")}
            value={amount}
            onChange={(e) => setAmount(e.target.value.replace(/\D/g, ""))}
          />
          <Button fullWidth loading={deposit.isPending} disabled={!insideTelegram} onClick={() => void handleSubmit()}>
            {t("starsDeposit.submitButton")}
          </Button>
        </div>
      )}
    </div>
  );
}
