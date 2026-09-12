import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button, Card, Input } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";
import type { CryptoCurrency } from "../../types/webapp";
import { copyToClipboard, formatNumber } from "../../lib/format";
import { useBalanceMethodsQuery, useDepositCryptoMutation } from "../../queries/useBalance";

const CRYPTO_OPTIONS: CryptoCurrency[] = ["trx", "usdt", "ton"];

function parseAmount(value: string): number {
  return parseInt(value.replace(/,/g, ""), 10) || 0;
}

export default function CryptoDeposit() {
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
      show(`مبلغ بین ${formatNumber(min)} تا ${formatNumber(max)} تومان وارد کنید.`, "error");
      return;
    }
    try {
      await deposit.mutateAsync({ amount: value, currency });
    } catch (err) {
      show(err instanceof Error ? err.message : "خطا", "error");
    }
  }

  return (
    <div>
      <PageHeader title="پرداخت ارزی" back="/balance" />

      {result?.ok ? (
        <Card className="space-y-4 p-5">
          <p className="font-medium text-success">فاکتور ایجاد شد. مبلغ را واریز کنید.</p>
          {result.order_id != null && (
            <p className="text-sm text-muted">
              شماره فاکتور: <span className="font-mono text-text">{result.order_id}</span>
            </p>
          )}
          {result.wallet_address && (
            <div>
              <p className="text-sm text-muted">آدرس کیف پول</p>
              <p className="break-all font-mono text-sm text-text">{result.wallet_address}</p>
              <Button
                variant="secondary"
                size="sm"
                className="mt-2"
                onClick={() => void copyToClipboard(result.wallet_address!)}
              >
                کپی آدرس
              </Button>
            </div>
          )}
          {result.amount_crypto && (
            <div>
              <p className="text-sm text-muted">مبلغ ({result.currency})</p>
              <p className="font-mono text-lg text-text">{result.amount_crypto}</p>
              <Button
                variant="secondary"
                size="sm"
                className="mt-2"
                onClick={() => void copyToClipboard(result.amount_crypto!)}
              >
                کپی مبلغ
              </Button>
            </div>
          )}
          {qrDataUrl && (
            <div className="flex justify-center pt-2">
              <img src={qrDataUrl} alt="QR" className="h-44 w-44 rounded-lg" />
            </div>
          )}
          <p className="text-xs text-muted">
            مهلت پرداخت حدود ۳۰ دقیقه است. پس از واریز، موجودی به‌صورت خودکار شارژ می‌شود.
          </p>
        </Card>
      ) : (
        <div className="space-y-4">
          <div>
            <p className="mb-2 text-sm text-muted">نوع ارز</p>
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
            مبلغ (تومان) بین {formatNumber(min)} تا {formatNumber(max)}
            {methods?.crypto_bonus_percent ? ` — بونوس ${methods.crypto_bonus_percent}%` : ""}
          </p>
          <Input
            inputMode="numeric"
            placeholder="مثال: 50000"
            value={amount}
            onChange={(e) => setAmount(e.target.value.replace(/\D/g, ""))}
          />
          <Button fullWidth loading={deposit.isPending} onClick={() => void handleSubmit()}>
            ایجاد فاکتور
          </Button>
        </div>
      )}
    </div>
  );
}
