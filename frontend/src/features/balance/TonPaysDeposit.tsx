import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button, Card, Input } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";
import { useAuth } from "../../context/AuthContext";
import { useTelegram } from "../../hooks/useTelegram";
import { copyToClipboard, formatNumber, formatToman } from "../../lib/format";
import {
  useBalanceMethodsQuery,
  useChangeTonPaysCardMutation,
  useCheckTonPaysMutation,
  useDepositTonPaysMutation,
  useOpenTonPaysInvoiceQuery,
  useSendTonPaysReceiptMutation,
} from "../../queries/useBalance";
import type { TonPaysInvoice } from "../../types/webapp";

const OPEN_STATUSES = ["pending", "processing", "need_action"];
const POLL_INTERVAL_MS = 10_000;

function parseAmount(value: string): number {
  return parseInt(value.replace(/,/g, ""), 10) || 0;
}

export default function TonPaysDeposit() {
  const { t } = useTranslation();
  const { refreshUser } = useAuth();
  const { webApp, openLink, haptic } = useTelegram();
  const { show } = useToast();
  const { data: methods } = useBalanceMethodsQuery();
  const openQuery = useOpenTonPaysInvoiceQuery(true);
  const deposit = useDepositTonPaysMutation();
  const check = useCheckTonPaysMutation();
  const changeCard = useChangeTonPaysCardMutation();
  const receipt = useSendTonPaysReceiptMutation();

  const [amount, setAmount] = useState("");
  const [invoice, setInvoice] = useState<TonPaysInvoice | null>(null);
  const [file, setFile] = useState<File | null>(null);

  const min = methods?.tonpays_deposit_min ?? 0;
  const max = methods?.tonpays_deposit_max ?? 0;
  const isOpen = !!invoice && OPEN_STATUSES.includes(invoice.status);

  useEffect(() => {
    if (!invoice && openQuery.data?.invoice) setInvoice(openQuery.data.invoice);
  }, [openQuery.data, invoice]);

  useEffect(() => {
    if (!invoice || !isOpen) return;
    const id = window.setInterval(() => {
      if (!check.isPending) void refresh(invoice.id, true);
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [invoice?.id, isOpen]);

  function applyInvoice(next: TonPaysInvoice | null | undefined) {
    if (!next) return;
    if (next.status === "completed" && invoice?.status !== "completed") {
      haptic.notify("success");
      show(t("tonpaysDeposit.paidToast"), "success");
      void refreshUser();
    }
    setInvoice(next);
  }

  async function refresh(id: number, silent = false) {
    try {
      const res = await check.mutateAsync(id);
      applyInvoice(res.invoice);
      if (!silent && res.invoice && res.invoice.status !== "completed") {
        show(t("tonpaysDeposit.statusToast", { status: res.invoice.status_label }), "info");
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
      applyInvoice(res.invoice);
    } catch (err) {
      show(err instanceof Error ? err.message : t("manualDeposit.genericError"), "error");
    }
  }

  function handlePay(current: TonPaysInvoice) {
    const telegramUrl = current.invoice_url;
    if (telegramUrl && telegramUrl.startsWith("https://t.me/") && webApp?.openTelegramLink) {
      webApp.openTelegramLink(telegramUrl);
      return;
    }
    const url = current.web_invoice_url || telegramUrl;
    if (url) openLink(url);
  }

  async function handleChangeCard(current: TonPaysInvoice) {
    try {
      const res = await changeCard.mutateAsync(current.id);
      applyInvoice(res.invoice);
      if (res.message) show(res.message, "info");
    } catch (err) {
      show(err instanceof Error ? err.message : t("manualDeposit.genericError"), "error");
    }
  }

  async function handleReceipt(current: TonPaysInvoice) {
    if (!file) return;
    try {
      const res = await receipt.mutateAsync({ invoice: current.id, file });
      applyInvoice(res.invoice);
      setFile(null);
      show(t("tonpaysDeposit.receiptSent"), "success");
    } catch (err) {
      show(err instanceof Error ? err.message : t("manualDeposit.receiptError"), "error");
    }
  }

  const payable = invoice ? invoice.final_amount || invoice.amount : 0;

  return (
    <div>
      <PageHeader title={t("tonpaysDeposit.title")} back="/balance" />

      {invoice ? (
        <Card className="space-y-4 p-5">
          {invoice.status === "completed" ? (
            <div className="space-y-1">
              <p className="font-medium text-success">{t("tonpaysDeposit.paidTitle")}</p>
              <p className="text-sm text-muted">{t("tonpaysDeposit.paidDesc")}</p>
            </div>
          ) : (
            <p className={`font-medium ${isOpen ? "text-text" : "text-danger"}`}>{invoice.status_label}</p>
          )}

          <div className="space-y-1 text-sm text-muted">
            {invoice.invoice_id && (
              <p>
                {t("cryptoDeposit.invoiceNumber")}:{" "}
                <span className="ltr-field font-mono text-text" dir="ltr">
                  {invoice.invoice_id}
                </span>
              </p>
            )}
            <p>
              {t("tonpaysDeposit.chargeAmount")}: {formatToman(invoice.amount)}
            </p>
            <div className="rounded-md border border-border p-3">
              <p className="mb-1">{t("tonpaysDeposit.payableAmount")}:</p>
              <p className="flex items-center justify-between gap-2">
                <span className="font-semibold text-text">
                  {formatNumber(payable * 10)} {t("tonpaysDeposit.rial")}
                </span>
                <Button variant="secondary" size="sm" onClick={() => void copyToClipboard(String(payable * 10))}>
                  {t("tonpaysDeposit.copyRial")}
                </Button>
              </p>
              <p className="mt-1 flex items-center justify-between gap-2">
                <span className="font-semibold text-text">{formatToman(payable)}</span>
                <Button variant="secondary" size="sm" onClick={() => void copyToClipboard(String(payable))}>
                  {t("tonpaysDeposit.copyToman")}
                </Button>
              </p>
            </div>
          </div>

          {isOpen && (
            <>
              <p className="rounded-md bg-warning/10 p-3 text-xs font-medium text-warning">
                {t("tonpaysDeposit.exactAmountWarning", {
                  rial: formatNumber(payable * 10),
                  toman: formatNumber(payable),
                })}
                <br />
                {t("tonpaysDeposit.bankUnitHint")}
              </p>

              {invoice.mode === "custom" ? (
                <div className="space-y-3">
                  <div>
                    <p className="text-sm text-muted">{t("manualDeposit.cardNumber")}</p>
                    <p className="ltr-field break-all font-mono text-text" dir="ltr">
                      {invoice.card_number || "—"}
                    </p>
                    {invoice.card_name && (
                      <p className="text-sm text-muted">
                        {t("manualDeposit.cardHolder")}: {invoice.card_name}
                      </p>
                    )}
                    <div className="mt-2 flex flex-wrap gap-2">
                      {invoice.card_number && (
                        <Button variant="secondary" size="sm" onClick={() => void copyToClipboard(invoice.card_number!)}>
                          {t("manualDeposit.copyCardNumber")}
                        </Button>
                      )}
                      <Button
                        variant="secondary"
                        size="sm"
                        loading={changeCard.isPending}
                        onClick={() => void handleChangeCard(invoice)}
                      >
                        {t("tonpaysDeposit.changeCard")}
                      </Button>
                    </div>
                  </div>
                  {invoice.receipt_sent ? (
                    <p className="text-sm text-muted">{t("tonpaysDeposit.receiptWaiting")}</p>
                  ) : (
                    <>
                      <label className="block text-sm">
                        <span className="mb-2 block text-muted">{t("manualDeposit.sendReceipt")}</span>
                        <input
                          type="file"
                          accept="image/*"
                          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                          className="block w-full text-sm text-muted file:ml-3 file:rounded-md file:border-0 file:bg-primary/10 file:px-3.5 file:py-2 file:text-sm file:font-medium file:text-primary hover:file:bg-primary/15"
                        />
                      </label>
                      <Button
                        fullWidth
                        loading={receipt.isPending}
                        disabled={!file}
                        onClick={() => void handleReceipt(invoice)}
                      >
                        {t("manualDeposit.submitReceipt")}
                      </Button>
                    </>
                  )}
                </div>
              ) : (
                <Button fullWidth onClick={() => handlePay(invoice)}>
                  {t("tonpaysDeposit.payButton")}
                </Button>
              )}

              <Button
                fullWidth
                variant="secondary"
                loading={check.isPending}
                onClick={() => void refresh(invoice.id)}
              >
                {t("tonpaysDeposit.checkButton")}
              </Button>
              <p className="text-xs text-muted">{t("tonpaysDeposit.autoCheckNote")}</p>
            </>
          )}

          {!isOpen && (
            <Button fullWidth variant="secondary" onClick={() => setInvoice(null)}>
              {t("tonpaysDeposit.newInvoice")}
            </Button>
          )}
        </Card>
      ) : (
        <div className="space-y-4">
          <p className="text-sm text-muted">
            {t("manualDeposit.amountRange", { min: formatNumber(min), max: formatNumber(max) })}
            {methods?.tonpays_bonus_percent ? t("manualDeposit.bonus", { percent: methods.tonpays_bonus_percent }) : ""}
          </p>
          <Input
            inputMode="numeric"
            placeholder={t("manualDeposit.amountPlaceholder")}
            value={amount}
            onChange={(e) => setAmount(e.target.value.replace(/\D/g, ""))}
          />
          <Button fullWidth loading={deposit.isPending} onClick={() => void handleCreate()}>
            {t("tonpaysDeposit.submitButton")}
          </Button>
        </div>
      )}
    </div>
  );
}
