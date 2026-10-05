import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { PageHeader } from "../../components/layout/PageHeader";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Copy,
  CreditCard,
  ExternalLink,
  Loader2,
  RefreshCw,
  Search,
  Upload,
} from "lucide-react";
import { Badge, Button, Card, Input } from "../../components/ui";
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

type BadgeTone = "primary" | "success" | "warning" | "danger" | "muted";

function statusTone(status: string): BadgeTone {
  if (status === "completed") return "success";
  if (status === "pending") return "warning";
  if (status === "processing" || status === "need_action") return "primary";
  return "danger";
}

/** Group a plain card number as 4-4-4-4; masked numbers from TonPays are shown as-is. */
function formatCardNumber(value?: string | null): string {
  if (!value) return "—";
  return /^\d+$/.test(value) ? value.replace(/(\d{4})(?=\d)/g, "$1 ") : value;
}

function AmountRow({
  value,
  unit,
  big = false,
  copyLabel,
  onCopy,
}: {
  value: string;
  unit: string;
  big?: boolean;
  copyLabel: string;
  onCopy: () => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <p className="flex items-baseline gap-1.5">
        <span className={`ltr-field font-mono font-semibold text-text ${big ? "text-2xl" : "text-base"}`} dir="ltr">
          {value}
        </span>
        <span className="text-sm text-muted">{unit}</span>
      </p>
      <button
        type="button"
        onClick={onCopy}
        className="flex shrink-0 items-center gap-1 rounded-lg bg-primary/10 px-2.5 py-1.5 text-xs font-medium text-primary hover:bg-primary/15"
      >
        <Copy size={13} />
        {copyLabel}
      </button>
    </div>
  );
}

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

  async function copyWithToast(text: string) {
    await copyToClipboard(text);
    haptic.notify("success");
    show(t("tonpaysDeposit.copied"), "success");
  }

  return (
    <div>
      <PageHeader title={t("tonpaysDeposit.title")} back="/balance" />

      {invoice ? (
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0">
              <p className="text-xs text-muted">{t("cryptoDeposit.invoiceNumber")}</p>
              <p className="ltr-field truncate font-mono text-sm text-text" dir="ltr">
                {invoice.invoice_id || "—"}
              </p>
            </div>
            <Badge tone={statusTone(invoice.status)}>{invoice.status_label}</Badge>
          </div>

          {invoice.status === "completed" && (
            <Card className="flex items-center gap-3 border-success/30 bg-success/10 p-4">
              <CheckCircle2 size={28} className="shrink-0 text-success" />
              <div>
                <p className="font-semibold text-success">{t("tonpaysDeposit.paidTitle")}</p>
                <p className="text-sm text-muted">{t("tonpaysDeposit.paidDesc")}</p>
              </div>
            </Card>
          )}

          {isOpen && invoice.mode === "custom" && (
            <div className="relative aspect-[1.6] w-full overflow-hidden rounded-2xl bg-[#26215C] p-5 text-[#EEEDFE] shadow-lg">
              <div className="pointer-events-none absolute -left-10 -top-12 h-40 w-40 rounded-full bg-white/5" />
              <div className="pointer-events-none absolute -bottom-16 -right-8 h-48 w-48 rounded-full bg-white/5" />
              <div className="relative flex h-full flex-col justify-between">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium tracking-wide text-[#CECBF6]">TonPays</span>
                  <CreditCard size={22} className="text-[#CECBF6]" />
                </div>
                <p className="ltr-field text-center font-mono text-lg tracking-[0.12em] sm:text-xl" dir="ltr">
                  {formatCardNumber(invoice.card_number)}
                </p>
                <div className="flex items-end justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-[11px] text-[#CECBF6]">{t("manualDeposit.cardHolder")}</p>
                    <p className="truncate text-sm font-medium">{invoice.card_name || "—"}</p>
                  </div>
                  {invoice.card_number && (
                    <button
                      type="button"
                      onClick={() => void copyWithToast(invoice.card_number!.replace(/\D/g, "") || invoice.card_number!)}
                      className="flex shrink-0 items-center gap-1 rounded-lg bg-white/10 px-3 py-1.5 text-xs font-medium hover:bg-white/20"
                    >
                      <Copy size={13} />
                      {t("tonpaysDeposit.copyCard")}
                    </button>
                  )}
                </div>
              </div>
            </div>
          )}

          <Card className="space-y-3 p-4">
            <p className="text-xs text-muted">
              {isOpen ? t("tonpaysDeposit.payableAmount") : t("tonpaysDeposit.chargeAmount")}
            </p>
            <AmountRow
              value={formatNumber(payable * 10)}
              unit={t("tonpaysDeposit.rial")}
              big
              copyLabel={t("tonpaysDeposit.copyRial")}
              onCopy={() => void copyWithToast(String(payable * 10))}
            />
            <div className="border-t border-border" />
            <AmountRow
              value={formatNumber(payable)}
              unit={t("common.toman")}
              copyLabel={t("tonpaysDeposit.copyToman")}
              onCopy={() => void copyWithToast(String(payable))}
            />
            {payable !== invoice.amount && (
              <p className="text-xs text-muted">
                {t("tonpaysDeposit.chargeAmount")}: {formatToman(invoice.amount)}
              </p>
            )}
          </Card>

          {isOpen && (
            <>
              <div className="flex items-start gap-2 rounded-xl border border-warning/30 bg-warning/10 p-3 text-xs leading-relaxed text-warning">
                <AlertTriangle size={15} className="mt-0.5 shrink-0" />
                <p>
                  <span className="font-semibold">
                    {t("tonpaysDeposit.exactAmountWarning", {
                      rial: formatNumber(payable * 10),
                      toman: formatNumber(payable),
                    })}
                  </span>{" "}
                  {t("tonpaysDeposit.bankUnitHint")}
                </p>
              </div>

              {invoice.mode === "custom" ? (
                <div className="space-y-3">
                  <Button
                    fullWidth
                    variant="secondary"
                    loading={changeCard.isPending}
                    onClick={() => void handleChangeCard(invoice)}
                  >
                    <RefreshCw size={15} />
                    {t("tonpaysDeposit.changeCard")}
                  </Button>
                  {invoice.receipt_sent ? (
                    <Card className="flex items-center gap-2 p-3 text-sm text-muted">
                      <Clock size={16} className="shrink-0" />
                      {t("tonpaysDeposit.receiptWaiting")}
                    </Card>
                  ) : (
                    <Card className="space-y-3 p-4">
                      <label className="flex cursor-pointer flex-col items-center gap-1.5 rounded-xl border border-dashed border-border px-3 py-5 text-center hover:border-primary/50">
                        <Upload size={20} className="text-primary" />
                        <span className="text-sm text-text">{file ? file.name : t("manualDeposit.sendReceipt")}</span>
                        <input
                          type="file"
                          accept="image/*"
                          className="hidden"
                          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
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
                    </Card>
                  )}
                </div>
              ) : (
                <Button fullWidth onClick={() => handlePay(invoice)}>
                  <ExternalLink size={15} />
                  {t("tonpaysDeposit.payButton")}
                </Button>
              )}

              <Button fullWidth variant="ghost" loading={check.isPending} onClick={() => void refresh(invoice.id)}>
                <Search size={15} />
                {t("tonpaysDeposit.checkButton")}
              </Button>
              <p className="flex items-center justify-center gap-1.5 text-xs text-muted">
                <Loader2 size={12} className="animate-spin" />
                {t("tonpaysDeposit.autoCheckNote")}
              </p>
            </>
          )}

          {!isOpen && (
            <Button fullWidth variant="secondary" onClick={() => setInvoice(null)}>
              {t("tonpaysDeposit.newInvoice")}
            </Button>
          )}
        </div>
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
