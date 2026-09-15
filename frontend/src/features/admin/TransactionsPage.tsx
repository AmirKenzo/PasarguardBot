import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Check, Coins, CreditCard, Eye, Maximize, Minimize, RotateCcw, ShieldAlert, X } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge, IconBadge, Input, Modal, Pagination, Skeleton } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";
import { formatToman, formatUnixDate } from "../../lib/format";
import { panelTransactionsApi } from "../../api/panel";
import type { PanelTransactionRow } from "../../types/panel";
import { useWebAppAuth } from "../../hooks/useWebAppAuth";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { ConfirmButton, SectionCard, SelectField, StatTile, Toolbar } from "./components";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

const METHOD_ICONS: Record<string, LucideIcon> = {
  manual_card: CreditCard,
  crypto: Coins,
};

const STATUS_TONE: Record<string, "success" | "warning" | "danger" | "muted" | "primary"> = {
  approved: "success",
  pending: "warning",
  rejected: "danger",
  needs_fix: "primary",
  expired: "muted",
};

const methodLabels = (t: TFunction): Record<string, string> => ({
  manual_card: t("panel.transactions.methodManualCard"),
  crypto: t("panel.transactions.methodCrypto"),
});

const statusLabels = (t: TFunction): Record<string, string> => ({
  pending: t("panel.transactions.statusPending"),
  approved: t("panel.transactions.statusApproved"),
  rejected: t("panel.transactions.statusRejected"),
  needs_fix: t("panel.transactions.statusNeedsFix"),
  expired: t("panel.transactions.statusExpired"),
});

const methodOptions = (t: TFunction) => [
  { value: "", label: t("panel.common.all") },
  { value: "manual_card", label: t("panel.transactions.methodManualCard") },
  { value: "crypto", label: t("panel.transactions.methodCrypto") },
];

const statusOptions = (t: TFunction) => [
  { value: "", label: t("panel.common.all") },
  { value: "pending", label: t("panel.transactions.statusPending") },
  { value: "approved", label: t("panel.transactions.statusApproved") },
  { value: "rejected", label: t("panel.transactions.statusRejected") },
  { value: "needs_fix", label: t("panel.transactions.statusNeedsFix") },
  { value: "expired", label: t("panel.transactions.statusExpired") },
];

const dayOptions = (t: TFunction) => [
  { value: "0", label: t("panel.transactions.dateAll") },
  { value: "1", label: t("panel.transactions.dateToday") },
  { value: "7", label: t("panel.transactions.date7d") },
  { value: "30", label: t("panel.transactions.date30d") },
];

const EMPTY_FILTERS = { txId: "", userId: "", amount: "", method: "", status: "", days: "0" };

export default function AdminTransactionsPage() {
  const { t } = useTranslation();
  const { auth } = useWebAppAuth();
  const toast = useToast();
  const queryClient = useQueryClient();

  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [draft, setDraft] = useState(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const [receiptFor, setReceiptFor] = useState<PanelTransactionRow | null>(null);
  const [receiptUrl, setReceiptUrl] = useState<string | null>(null);
  const [receiptLoading, setReceiptLoading] = useState(false);
  const [receiptFullscreen, setReceiptFullscreen] = useState(false);
  const receiptImgRef = useRef<HTMLImageElement>(null);

  useEffect(() => {
    const onChange = () => setReceiptFullscreen(document.fullscreenElement === receiptImgRef.current);
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);

  function toggleReceiptFullscreen() {
    if (document.fullscreenElement) {
      void document.exitFullscreen();
    } else {
      void receiptImgRef.current?.requestFullscreen();
    }
  }

  const query = usePanelQuery(
    ["transactions", filters.txId, filters.userId, filters.amount, filters.method, filters.status, filters.days, page],
    (a) =>
      panelTransactionsApi.listTransactions({
        ...a,
        tx_id: filters.txId,
        user_id: filters.userId,
        amount: filters.amount,
        method: filters.method,
        status: filters.status,
        days: Number(filters.days) || 0,
        page,
        limit: 15,
      })
  );

  const invalidate = [["transactions"], ["me"], ["dashboard"]];
  const approve = usePanelAction(panelTransactionsApi.approve, { invalidate });
  const reject = usePanelAction(panelTransactionsApi.reject, { invalidate });
  const requestFix = usePanelAction(panelTransactionsApi.requestFix, { invalidate });
  const reportMismatch = usePanelAction(panelTransactionsApi.reportMismatch, { invalidate });

  const rows = query.data?.transactions || [];
  const stats = query.data?.stats;

  function applyFilters() {
    setPage(1);
    setFilters(draft);
  }
  function clearFilters() {
    setDraft(EMPTY_FILTERS);
    setFilters(EMPTY_FILTERS);
    setPage(1);
  }

  async function openReceipt(row: PanelTransactionRow) {
    if (!auth) return;
    setReceiptFor(row);
    setReceiptUrl(null);
    setReceiptLoading(true);
    try {
      const result = await panelTransactionsApi.receiptLink({ ...auth, tx_id: Number(row.id) });
      setReceiptUrl(result.url || null);
    } catch (error) {
      toast.show(error instanceof Error ? error.message : t("panel.transactions.receiptLoadError"), "error");
      setReceiptFor(null);
    } finally {
      setReceiptLoading(false);
    }
  }

  function afterAction() {
    void queryClient.invalidateQueries({ queryKey: ["panel", "transactions"] });
  }

  return (
    <>
      <PageHeader title={t("panel.common.transactions")} subtitle={t("panel.transactions.subtitle")} />

      {stats && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatTile label={t("panel.transactions.statPending")} value={stats.pending} icon={CreditCard} tone={stats.pending ? "warning" : "default"} />
          <StatTile label={t("panel.transactions.statApproved7d")} value={stats.approved_7d} icon={Check} tone="success" />
          <StatTile label={t("panel.transactions.statRejected7d")} value={stats.rejected_7d} icon={X} tone="danger" />
          <StatTile
            label={t("panel.transactions.statVolume7d")}
            value={
              <span className="ltr-field">
                {stats.approved_volume_7d.toLocaleString("en-US")} {t("common.toman")}
              </span>
            }
            icon={Coins}
            tone="primary"
          />
        </div>
      )}

      <SectionCard title={t("panel.transactions.title")}>
        <Toolbar onSubmit={applyFilters}>
          <div className="w-36"><Input label={t("panel.transactions.filterTxId")} ltr value={draft.txId} onChange={(e) => setDraft({ ...draft, txId: e.target.value })} /></div>
          <div className="w-40"><Input label={t("panel.transactions.filterUserId")} ltr value={draft.userId} onChange={(e) => setDraft({ ...draft, userId: e.target.value })} /></div>
          <div className="w-40"><Input label={t("panel.transactions.filterAmount")} ltr value={draft.amount} onChange={(e) => setDraft({ ...draft, amount: e.target.value })} /></div>
          <div className="w-44"><SelectField label={t("panel.transactions.paymentMethod")} options={methodOptions(t)} value={draft.method} onChange={(e) => setDraft({ ...draft, method: e.target.value })} /></div>
          <div className="w-40"><SelectField label={t("panel.common.status")} options={statusOptions(t)} value={draft.status} onChange={(e) => setDraft({ ...draft, status: e.target.value })} /></div>
          <div className="w-36"><SelectField label={t("panel.transactions.dateRange")} options={dayOptions(t)} value={draft.days} onChange={(e) => setDraft({ ...draft, days: e.target.value })} /></div>
          <button type="submit" className="h-11 rounded-md bg-primary px-5 text-sm font-semibold text-primary-text">
            {t("panel.common.applyFilter")}
          </button>
          <button type="button" onClick={clearFilters} className="h-11 text-sm font-semibold text-muted hover:text-text">
            {t("panel.transactions.clearFilters")}
          </button>
        </Toolbar>

        {query.isError ? (
          <p className="py-6 text-center text-sm text-danger">{query.error.message}</p>
        ) : query.isLoading ? (
          <div className="mt-4 space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-14 w-full rounded-md" />
            ))}
          </div>
        ) : rows.length ? (
          <div className="mt-2 divide-y divide-border/60">
            {rows.map((row) => {
              const Icon = METHOD_ICONS[row.method] ?? CreditCard;
              const isManualPending = row.source === "tx" && row.method === "manual_card" && row.status === "pending";
              const isAutomatic = row.method !== "manual_card";
              return (
                <div key={`${row.source}-${row.id}`} className="flex flex-wrap items-center gap-3 py-3 first:pt-0 last:pb-0">
                  <IconBadge icon={Icon} tone="muted" size="sm" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 text-sm font-semibold text-text">
                      {methodLabels(t)[row.method] || row.method}
                      <span className="ltr-field text-xs font-normal text-muted">#{row.id}</span>
                    </div>
                    <div className="text-xs text-muted">
                      {t("common.user")} <span className="ltr-field">{row.user_id ?? "—"}</span>
                      {row.created_at ? ` · ${formatUnixDate(row.created_at)}` : ""}
                    </div>
                  </div>
                  <div className="text-sm font-bold ltr-field">{formatToman(row.amount)}</div>
                  <Badge tone={STATUS_TONE[row.status] || "muted"}>{statusLabels(t)[row.status] || row.status}</Badge>
                  <div className="flex shrink-0 items-center gap-1">
                    {row.has_receipt && (
                      <button
                        title={t("panel.transactions.viewReceipt")}
                        onClick={() => void openReceipt(row)}
                        className="flex h-8 w-8 items-center justify-center rounded-md border border-border text-muted transition-colors hover:border-primary/40 hover:bg-primary/10 hover:text-primary"
                      >
                        <Eye size={14} />
                      </button>
                    )}
                    {isManualPending ? (
                      <>
                        <ConfirmButton
                          size="sm"
                          variant="ghost"
                          className="!px-2 text-success hover:bg-success/10"
                          title={t("panel.transactions.approveAction")}
                          message={t("panel.transactions.approveConfirm", { id: row.id, amount: formatToman(row.amount) })}
                          onConfirm={() => approve.mutate({ tx_id: Number(row.id) }, { onSuccess: afterAction })}
                        >
                          <Check size={14} />
                        </ConfirmButton>
                        <ConfirmButton
                          size="sm"
                          variant="ghost"
                          className="!px-2 text-danger hover:bg-danger/10"
                          title={t("panel.transactions.rejectAction")}
                          message={t("panel.transactions.rejectConfirm", { id: row.id })}
                          onConfirm={() => reject.mutate({ tx_id: Number(row.id) }, { onSuccess: afterAction })}
                        >
                          <X size={14} />
                        </ConfirmButton>
                        <ConfirmButton
                          size="sm"
                          variant="ghost"
                          className="!px-2 hover:bg-primary/10 hover:text-primary"
                          title={t("panel.transactions.fixAction")}
                          message={t("panel.transactions.fixConfirm", { id: row.id })}
                          onConfirm={() => requestFix.mutate({ tx_id: Number(row.id) }, { onSuccess: afterAction })}
                        >
                          <RotateCcw size={14} />
                        </ConfirmButton>
                        <ConfirmButton
                          size="sm"
                          variant="ghost"
                          className="!px-2 text-warning hover:bg-warning/10"
                          title={t("panel.transactions.mismatchAction")}
                          message={t("panel.transactions.mismatchConfirm", { id: row.id })}
                          onConfirm={() => reportMismatch.mutate({ tx_id: Number(row.id) }, { onSuccess: afterAction })}
                        >
                          <ShieldAlert size={14} />
                        </ConfirmButton>
                      </>
                    ) : (
                      isAutomatic && <span className="text-xs text-muted">{t("panel.transactions.automatic")}</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="py-8 text-center text-sm text-muted">{t("panel.transactions.empty")}</p>
        )}

        <div className="mt-4">
          <Pagination page={page} totalPages={query.data?.meta.total_pages || 1} onChange={setPage} />
        </div>
      </SectionCard>

      <Modal
        open={receiptFor != null}
        onClose={() => {
          if (document.fullscreenElement) void document.exitFullscreen();
          setReceiptFor(null);
        }}
        title={t("panel.transactions.receiptTitle", { id: receiptFor?.id })}
        size="lg"
      >
        <div className="relative flex max-h-[75vh] min-h-[40vh] items-center justify-center overflow-hidden rounded-md bg-surface-2">
          {receiptLoading ? (
            <Skeleton className="h-full w-full" />
          ) : receiptUrl ? (
            <>
              <img
                ref={receiptImgRef}
                src={receiptUrl}
                alt=""
                className="max-h-[75vh] max-w-full object-contain [&:fullscreen]:h-screen [&:fullscreen]:max-h-none [&:fullscreen]:w-screen [&:fullscreen]:max-w-none [&:fullscreen]:bg-black [&:fullscreen]:object-contain"
              />
              <button
                onClick={toggleReceiptFullscreen}
                title={t(receiptFullscreen ? "panel.transactions.exitFullscreen" : "panel.transactions.fullscreen")}
                className="absolute left-2 top-2 flex h-8 w-8 items-center justify-center rounded-md bg-black/55 text-white backdrop-blur-sm transition-colors hover:bg-black/70"
              >
                {receiptFullscreen ? <Minimize size={14} /> : <Maximize size={14} />}
              </button>
            </>
          ) : (
            <span className="text-xs text-muted">{t("panel.transactions.receiptLoadError")}</span>
          )}
        </div>
        <p className="mt-2 text-xs text-muted">{t("panel.transactions.receiptStreamNote")}</p>
      </Modal>
    </>
  );
}
