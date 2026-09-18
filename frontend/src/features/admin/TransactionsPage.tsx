import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  Banknote,
  Calendar,
  CalendarClock,
  CalendarDays,
  CalendarRange,
  Check,
  Coins,
  CreditCard,
  Eye,
  Filter,
  Maximize,
  Minimize,
  RotateCcw,
  SlidersHorizontal,
  ShieldAlert,
  User,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge, IconBadge, Input, Modal, Pagination, Skeleton } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";
import { formatToman, formatUnixDate } from "../../lib/format";
import { panelTransactionsApi } from "../../api/panel";
import type { PanelTransactionRow } from "../../types/panel";
import { useWebAppAuth } from "../../hooks/useWebAppAuth";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { AutoRefreshMenu, ConfirmButton, IconMenuButton, MenuDivider, MenuHeader, MenuRow, SectionCard, StatTile } from "./components";
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

const TAB_ACTIVE_CLASSES: Record<"success" | "warning" | "danger" | "muted" | "primary", string> = {
  primary: "bg-primary/12 text-primary",
  success: "bg-success/12 text-success",
  warning: "bg-warning/12 text-warning",
  danger: "bg-danger/12 text-danger",
  muted: "bg-surface-2 text-text",
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

/** Quick top-level tabs — the one filter dimension used often enough to skip the modal. */
const statusTabs = (t: TFunction) => [
  { value: "", label: t("panel.common.all"), tone: "muted" as const },
  { value: "pending", label: t("panel.transactions.statusPending"), tone: "warning" as const },
  { value: "approved", label: t("panel.transactions.statusApproved"), tone: "success" as const },
  { value: "rejected", label: t("panel.transactions.statusRejected"), tone: "danger" as const },
  { value: "needs_fix", label: t("panel.transactions.statusNeedsFix"), tone: "primary" as const },
  { value: "expired", label: t("panel.transactions.statusExpired"), tone: "muted" as const },
];

/** Less-common filters live in the compact "more filters" dropdown instead of cluttering the toolbar. */
const methodOptions = (t: TFunction) => [
  { value: "", label: t("panel.common.all"), icon: Filter },
  { value: "manual_card", label: t("panel.transactions.methodManualCard"), icon: CreditCard },
  { value: "crypto", label: t("panel.transactions.methodCrypto"), icon: Coins },
];

const dayOptions = (t: TFunction) => [
  { value: "0", label: t("panel.transactions.dateAll"), icon: Calendar },
  { value: "1", label: t("panel.transactions.dateToday"), icon: CalendarClock },
  { value: "7", label: t("panel.transactions.date7d"), icon: CalendarRange },
  { value: "30", label: t("panel.transactions.date30d"), icon: CalendarDays },
];

const refreshOptions = (t: TFunction) => [
  { value: 0, label: t("panel.transactions.refreshManual") },
  { value: 5000, label: t("panel.transactions.refresh5s") },
  { value: 15000, label: t("panel.transactions.refresh15s") },
  { value: 30000, label: t("panel.transactions.refresh30s") },
  { value: 60000, label: t("panel.transactions.refresh1m") },
];

const EMPTY_FILTERS = { userId: "", amount: "", method: "", status: "", days: "0" };
const EMPTY_SEARCH = { userId: "", amount: "" };
const SEARCH_DEBOUNCE_MS = 400;
const AUTO_REFRESH_STORAGE_KEY = "admin.transactions.autoRefreshMs";

function loadAutoRefreshMs(): number {
  try {
    const raw = Number(localStorage.getItem(AUTO_REFRESH_STORAGE_KEY));
    return Number.isFinite(raw) && raw >= 0 ? raw : 0;
  } catch {
    return 0;
  }
}

export default function AdminTransactionsPage() {
  const { t } = useTranslation();
  const { auth } = useWebAppAuth();
  const toast = useToast();
  const queryClient = useQueryClient();

  // Free-text fields are debounced so typing doesn't fire a request per
  // keystroke; chip filters apply straight to `filters` since they're
  // discrete clicks already.
  const [searchInputs, setSearchInputs] = useState(EMPTY_SEARCH);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const [autoRefreshMs, setAutoRefreshMs] = useState(loadAutoRefreshMs);
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

  useEffect(() => {
    const handle = setTimeout(() => {
      setFilters((prev) => ({ ...prev, ...searchInputs }));
      setPage(1);
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(handle);
  }, [searchInputs]);

  useEffect(() => {
    try {
      localStorage.setItem(AUTO_REFRESH_STORAGE_KEY, String(autoRefreshMs));
    } catch {
      // Private browsing / storage disabled — auto-refresh still works for this session.
    }
  }, [autoRefreshMs]);

  function toggleReceiptFullscreen() {
    if (document.fullscreenElement) {
      void document.exitFullscreen();
    } else {
      void receiptImgRef.current?.requestFullscreen();
    }
  }

  const query = usePanelQuery(
    ["transactions", filters.userId, filters.amount, filters.method, filters.status, filters.days, page],
    (a) =>
      panelTransactionsApi.listTransactions({
        ...a,
        user_id: filters.userId,
        amount: filters.amount,
        method: filters.method,
        status: filters.status,
        days: Number(filters.days) || 0,
        page,
        limit: 15,
      }),
    { refetchInterval: autoRefreshMs || false }
  );

  const invalidate = [["transactions"], ["me"], ["dashboard"]];
  const approve = usePanelAction(panelTransactionsApi.approve, { invalidate });
  const reject = usePanelAction(panelTransactionsApi.reject, { invalidate });
  const requestFix = usePanelAction(panelTransactionsApi.requestFix, { invalidate });
  const reportMismatch = usePanelAction(panelTransactionsApi.reportMismatch, { invalidate });

  const rows = query.data?.transactions || [];
  const stats = query.data?.stats;

  function updateFilter(key: "method" | "status" | "days", value: string) {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  }
  function clearFilters() {
    setSearchInputs(EMPTY_SEARCH);
    setFilters(EMPTY_FILTERS);
    setPage(1);
  }

  const hasAdvancedFilters = filters.method !== "" || filters.days !== "0";
  const hasActiveFilters =
    searchInputs.userId !== "" || searchInputs.amount !== "" || filters.status !== "" || hasAdvancedFilters;

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
        <div className="space-y-2 rounded-lg border border-border bg-surface p-2.5">
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative w-28">
              <User size={13} className="pointer-events-none absolute top-1/2 -translate-y-1/2 text-muted ltr:left-2.5 rtl:right-2.5" />
              <Input
                dense
                ltr
                placeholder={t("panel.transactions.filterUserId")}
                aria-label={t("panel.transactions.filterUserId")}
                className="ltr:pl-7 rtl:pr-7"
                value={searchInputs.userId}
                onChange={(e) => setSearchInputs((s) => ({ ...s, userId: e.target.value }))}
              />
            </div>
            <div className="relative w-32">
              <Banknote size={13} className="pointer-events-none absolute top-1/2 -translate-y-1/2 text-muted ltr:left-2.5 rtl:right-2.5" />
              <Input
                dense
                ltr
                placeholder={t("panel.transactions.filterAmount")}
                aria-label={t("panel.transactions.filterAmount")}
                className="ltr:pl-7 rtl:pr-7"
                value={searchInputs.amount}
                onChange={(e) => setSearchInputs((s) => ({ ...s, amount: e.target.value }))}
              />
            </div>

            <IconMenuButton
              icon={SlidersHorizontal}
              title={t("panel.transactions.advancedFilters")}
              active={hasAdvancedFilters}
              badge={hasAdvancedFilters}
              width={208}
              heightEstimate={320}
            >
              {(close) => (
                <>
                  <MenuHeader title={t("panel.transactions.paymentMethod")} />
                  {methodOptions(t).map((opt) => (
                    <MenuRow
                      key={opt.value}
                      icon={opt.icon}
                      label={opt.label}
                      active={opt.value === filters.method}
                      onClick={() => {
                        updateFilter("method", opt.value);
                        close();
                      }}
                    />
                  ))}
                  <MenuDivider />
                  <MenuHeader title={t("panel.transactions.dateRange")} />
                  {dayOptions(t).map((opt) => (
                    <MenuRow
                      key={opt.value}
                      icon={opt.icon}
                      label={opt.label}
                      active={opt.value === filters.days}
                      onClick={() => {
                        updateFilter("days", opt.value);
                        close();
                      }}
                    />
                  ))}
                </>
              )}
            </IconMenuButton>

            <AutoRefreshMenu
              options={refreshOptions(t)}
              value={autoRefreshMs}
              onChange={setAutoRefreshMs}
              onRefreshNow={() => void query.refetch()}
              isRefreshing={query.isFetching}
            />

            {hasActiveFilters && (
              <button
                type="button"
                onClick={clearFilters}
                title={t("panel.transactions.clearFilters")}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted transition-colors hover:bg-danger/10 hover:text-danger"
              >
                <X size={14} />
              </button>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-1">
            {statusTabs(t).map((tab) => {
              const active = tab.value === filters.status;
              return (
                <button
                  key={tab.value}
                  type="button"
                  onClick={() => updateFilter("status", tab.value)}
                  className={`shrink-0 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
                    active ? TAB_ACTIVE_CLASSES[tab.tone] : "text-muted hover:bg-surface-2 hover:text-text"
                  }`}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>

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
