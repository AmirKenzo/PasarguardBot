import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button, Card, Input } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";
import { copyToClipboard, formatNumber } from "../../lib/format";
import {
  useBalanceMethodsQuery,
  useDepositManualMutation,
  useDepositManualReceiptMutation,
  useRequestPhoneVerificationMutation,
} from "../../queries/useBalance";

function parseAmount(value: string): number {
  return parseInt(value.replace(/,/g, ""), 10) || 0;
}

const PHONE_VERIFY_POLL_MS = 2000;
const PHONE_VERIFY_TIMEOUT_MS = 30000;

export default function ManualDeposit() {
  const { t } = useTranslation();
  const { data: methods, refetch: refetchMethods } = useBalanceMethodsQuery();
  const deposit = useDepositManualMutation();
  const receipt = useDepositManualReceiptMutation();
  const requestPhone = useRequestPhoneVerificationMutation();
  const { show } = useToast();
  const [amount, setAmount] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [receiptSent, setReceiptSent] = useState(false);
  const [verifyingPhone, setVerifyingPhone] = useState(false);
  const [confirmedAmount, setConfirmedAmount] = useState<number | null>(null);

  const result = deposit.data;
  const min = methods?.manual_deposit_min ?? 0;
  const max = methods?.manual_deposit_max ?? 0;

  // Poll the methods endpoint while waiting for the bot to receive the
  // shared contact — Telegram delivers it as a normal message, not a
  // direct API response, so there's no other way to know it landed.
  useEffect(() => {
    if (!verifyingPhone) return;
    const interval = setInterval(() => void refetchMethods(), PHONE_VERIFY_POLL_MS);
    const timeout = setTimeout(() => {
      setVerifyingPhone(false);
      show(t("manualDeposit.phoneVerifyTimeout"), "error");
    }, PHONE_VERIFY_TIMEOUT_MS);
    return () => {
      clearInterval(interval);
      clearTimeout(timeout);
    };
  }, [verifyingPhone, refetchMethods, show, t]);

  useEffect(() => {
    if (verifyingPhone && methods && !methods.phone_verify_required) {
      setVerifyingPhone(false);
      show(t("manualDeposit.phoneVerifySuccess"), "success");
    }
  }, [verifyingPhone, methods, show, t]);

  async function handleShareContact() {
    const tg = window.Telegram?.WebApp;
    if (!tg?.requestContact) {
      show(t("manualDeposit.phoneVerifyUnsupported"), "error");
      return;
    }
    try {
      await requestPhone.mutateAsync();
    } catch (err) {
      show(err instanceof Error ? err.message : t("manualDeposit.genericError"), "error");
      return;
    }
    tg.requestContact((sent) => {
      if (!sent) {
        show(t("manualDeposit.phoneVerifyCancelled"), "info");
        return;
      }
      setVerifyingPhone(true);
    });
  }

  async function handleSubmit() {
    const value = parseAmount(amount);
    if (value < min || value > max) {
      show(t("manualDeposit.amountRangeError", { min: formatNumber(min), max: formatNumber(max) }), "error");
      return;
    }
    try {
      await deposit.mutateAsync(value);
      setConfirmedAmount(value);
    } catch (err) {
      show(err instanceof Error ? err.message : t("manualDeposit.genericError"), "error");
    }
  }

  async function handleReceiptSubmit() {
    if (!confirmedAmount || !file) return;
    try {
      await receipt.mutateAsync({ amount: confirmedAmount, file });
      setReceiptSent(true);
      show(t("manualDeposit.receiptSuccess"), "success");
    } catch (err) {
      show(err instanceof Error ? err.message : t("manualDeposit.receiptError"), "error");
    }
  }

  return (
    <div>
      <PageHeader title={t("manualDeposit.title")} back="/balance" />

      {receiptSent ? (
        <Card className="space-y-2 p-5">
          <p className="font-medium text-success">{t("manualDeposit.receiptSent")}</p>
          <p className="text-sm text-muted">{t("manualDeposit.receiptSentDesc")}</p>
        </Card>
      ) : confirmedAmount != null ? (
        <Card className="space-y-4 p-5">
          <p className="font-medium text-success">{result?.message ?? t("manualDeposit.requestRegistered")}</p>
          {result?.card_number && (
            <div>
              <p className="text-sm text-muted">{t("manualDeposit.cardNumber")}</p>
              <p className="break-all font-mono text-text">{result.card_number}</p>
              {result.card_name && (
                <p className="text-sm text-muted">
                  {t("manualDeposit.cardHolder")}: {result.card_name}
                </p>
              )}
              <Button
                variant="secondary"
                size="sm"
                className="mt-2"
                onClick={() => void copyToClipboard(result.card_number!)}
              >
                {t("manualDeposit.copyCardNumber")}
              </Button>
            </div>
          )}
          <p className="border-t border-border pt-3 text-xs text-muted">{t("manualDeposit.afterDeposit")}</p>
          <label className="block text-sm">
            <span className="mb-2 block text-muted">{t("manualDeposit.sendReceipt")}</span>
            <input
              type="file"
              accept="image/*"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="block w-full text-sm text-muted file:ml-3 file:rounded-md file:border-0 file:bg-primary/10 file:px-3.5 file:py-2 file:text-sm file:font-medium file:text-primary hover:file:bg-primary/15"
            />
          </label>
          <Button fullWidth loading={receipt.isPending} disabled={!file} onClick={() => void handleReceiptSubmit()}>
            {t("manualDeposit.submitReceipt")}
          </Button>
        </Card>
      ) : methods?.phone_verify_required ? (
        <Card className="space-y-3 p-5 text-center">
          <p className="font-medium text-text">{t("manualDeposit.phoneVerifyTitle")}</p>
          <p className="text-sm text-muted">{t("manualDeposit.phoneVerifyDesc")}</p>
          <Button
            fullWidth
            loading={verifyingPhone || requestPhone.isPending}
            onClick={() => void handleShareContact()}
          >
            {verifyingPhone ? t("manualDeposit.phoneVerifyWaiting") : t("manualDeposit.phoneVerifyButton")}
          </Button>
        </Card>
      ) : (
        <div className="space-y-4">
          {methods?.card_number && methods.card_name && (
            <Card className="p-4">
              <p className="text-sm text-muted">{t("manualDeposit.cardNumber")}</p>
              <p className="break-all font-mono text-text">{methods.card_number}</p>
              <p className="mt-2 text-sm text-muted">
                {t("manualDeposit.cardHolder")}: {methods.card_name}
              </p>
            </Card>
          )}
          <p className="text-sm text-muted">
            {t("manualDeposit.amountRange", { min: formatNumber(min), max: formatNumber(max) })}
            {methods?.manual_bonus_percent ? t("manualDeposit.bonus", { percent: methods.manual_bonus_percent }) : ""}
          </p>
          <Input
            inputMode="numeric"
            placeholder={t("manualDeposit.amountPlaceholder")}
            value={amount}
            onChange={(e) => setAmount(e.target.value.replace(/\D/g, ""))}
          />
          <Button fullWidth loading={deposit.isPending} onClick={() => void handleSubmit()}>
            {t("manualDeposit.submitDeposit")}
          </Button>
        </div>
      )}
    </div>
  );
}
