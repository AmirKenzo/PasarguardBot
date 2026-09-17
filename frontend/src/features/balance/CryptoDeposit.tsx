import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { useTranslation } from "react-i18next";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button, Card, Input } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";
import type { CryptoCurrency } from "../../types/webapp";
import { copyToClipboard, formatNumber } from "../../lib/format";
import { useBalanceMethodsQuery, useDepositCryptoMutation } from "../../queries/useBalance";

const CRYPTO_OPTIONS: CryptoCurrency[] = ["trx", "usdt", "usdt-ton", "usdt-bep20", "ton", "pol"];

function parseAmount(value: string): number {
  return parseInt(value.replace(/,/g, ""), 10) || 0;
}

export default function CryptoDeposit() {
  const { t } = useTranslation();
  const { data: methods } = useBalanceMethodsQuery();
  const deposit = useDepositCryptoMutation();
  const { show } = useToast();
  const [currency, setCurrency] = useState<CryptoCurrency>("trx");
  const [amount, setAmount] = useState("");
  const [qrDataUrl, setQrDataUrl] = useState<string | null>(null);

  const result = deposit.data;
  const min = methods?.crypto_deposit_min ?? 0;
  const max = methods?.crypto_deposit_max ?? 0;

  useEffect(() => {
    if (!result?.wallet_address || !result.amount_crypto || !result.currency) {
      setQrDataUrl(null);
      return;
    }
    const payload = `${result.currency}:${result.wallet_address}?amount=${result.amount_crypto}`;
    void QRCode.toDataURL(payload, { width: 176, margin: 1 }).then(setQrDataUrl).catch(() => setQrDataUrl(null));
  }, [result?.wallet_address, result?.amount_crypto, result?.currency]);

  async function handleSubmit() {
    const value = parseAmount(amount);
    if (value < min || value > max) {
      show(t("cryptoDeposit.amountRangeError", { min: formatNumber(min), max: formatNumber(max) }), "error");
      return;
    }
    try {
      await deposit.mutateAsync({ amount: value, currency });
    } catch (err) {
      show(err instanceof Error ? err.message : t("cryptoDeposit.genericError"), "error");
    }
  }

  return (
    <div>
      <PageHeader title={t("cryptoDeposit.title")} back="/balance" />

      {result?.ok ? (
        <Card className="space-y-4 p-5">
          <p className="font-medium text-success">{t("cryptoDeposit.invoiceCreated")}</p>
          {result.order_id != null && (
            <p className="text-sm text-muted">
              {t("cryptoDeposit.invoiceNumber")}: <span className="font-mono text-text">{result.order_id}</span>
            </p>
          )}
          {result.wallet_address && (
            <div>
              <p className="text-sm text-muted">{t("cryptoDeposit.walletAddress")}</p>
              <p className="break-all font-mono text-sm text-text">{result.wallet_address}</p>
              <Button
                variant="secondary"
                size="sm"
                className="mt-2"
                onClick={() => void copyToClipboard(result.wallet_address!)}
              >
                {t("cryptoDeposit.copyAddress")}
              </Button>
            </div>
          )}
          {result.amount_crypto && (
            <div>
              <p className="text-sm text-muted">{t("cryptoDeposit.amountFor", { currency: result.currency })}</p>
              <p className="font-mono text-lg text-text">{result.amount_crypto}</p>
              <Button
                variant="secondary"
                size="sm"
                className="mt-2"
                onClick={() => void copyToClipboard(result.amount_crypto!)}
              >
                {t("cryptoDeposit.copyAmount")}
              </Button>
            </div>
          )}
          {qrDataUrl && (
            <div className="flex justify-center pt-2">
              <img src={qrDataUrl} alt="QR" className="h-44 w-44 rounded-lg" />
            </div>
          )}
          <p className="text-xs text-muted">{t("cryptoDeposit.paymentDeadline")}</p>
        </Card>
      ) : (
        <div className="space-y-4">
          <div>
            <p className="mb-2 text-sm text-muted">{t("cryptoDeposit.currencyType")}</p>
            <div className="flex gap-2">
              {CRYPTO_OPTIONS.map((c) => (
                <Button
                  key={c}
                  type="button"
                  size="sm"
                  variant={currency === c ? "primary" : "secondary"}
                  onClick={() => setCurrency(c)}
                >
                  {c.toUpperCase()}
                </Button>
              ))}
            </div>
          </div>
          <p className="text-sm text-muted">
            {t("cryptoDeposit.amountRange", { min: formatNumber(min), max: formatNumber(max) })}
            {methods?.crypto_bonus_percent ? t("cryptoDeposit.bonus", { percent: methods.crypto_bonus_percent }) : ""}
          </p>
          <Input
            inputMode="numeric"
            placeholder={t("cryptoDeposit.amountPlaceholder")}
            value={amount}
            onChange={(e) => setAmount(e.target.value.replace(/\D/g, ""))}
          />
          <Button fullWidth loading={deposit.isPending} onClick={() => void handleSubmit()}>
            {t("cryptoDeposit.createInvoice")}
          </Button>
        </div>
      )}
    </div>
  );
}
