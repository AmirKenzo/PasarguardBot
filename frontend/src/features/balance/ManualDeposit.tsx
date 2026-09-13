import { useState } from "react";
import { useTranslation } from "react-i18next";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button, Card, Input } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";
import { copyToClipboard, formatNumber } from "../../lib/format";
import {
  useBalanceMethodsQuery,
  useDepositManualMutation,
  useDepositManualReceiptMutation,
} from "../../queries/useBalance";

function parseAmount(value: string): number {
  return parseInt(value.replace(/,/g, ""), 10) || 0;
}

export default function ManualDeposit() {
  const { t } = useTranslation();
  const { data: methods } = useBalanceMethodsQuery();
  const deposit = useDepositManualMutation();
  const receipt = useDepositManualReceiptMutation();
  const { show } = useToast();
  const [amount, setAmount] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [receiptSent, setReceiptSent] = useState(false);

  const result = deposit.data;
  const min = methods?.manual_deposit_min ?? 0;
  const max = methods?.manual_deposit_max ?? 0;

  async function handleSubmit() {
    const value = parseAmount(amount);
    if (value < min || value > max) {
      show(t("manualDeposit.amountRangeError", { min: formatNumber(min), max: formatNumber(max) }), "error");
      return;
    }
    try {
      await deposit.mutateAsync(value);
    } catch (err) {
      show(err instanceof Error ? err.message : t("manualDeposit.genericError"), "error");
    }
  }

  async function handleReceiptSubmit() {
    if (!result?.tx_id || !file) return;
    try {
      await receipt.mutateAsync({ txId: result.tx_id, file });
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
      ) : result?.tx_id != null ? (
        <Card className="space-y-4 p-5">
          <p className="font-medium text-success">{result.message ?? t("manualDeposit.requestRegistered")}</p>
          {result.card_number && (
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
