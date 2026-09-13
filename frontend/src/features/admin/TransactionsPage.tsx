import { useState } from "react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge, Button, ErrorState, Pagination } from "../../components/ui";
import { formatNumber, formatToman, formatUnixDate } from "../../lib/format";
import { panelTransactionsApi } from "../../api/panel";
import type { PanelTransactionRow } from "../../types/panel";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { ConfirmButton, DataTable, SectionCard, SelectField, Toolbar } from "./components";
import type { Column } from "./components";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

const statusOptions = (t: TFunction) => [
  { value: "", label: t("panel.common.all") },
  { value: "pending", label: t("transaction.pending") },
  { value: "approved", label: t("panel.transactions.approved") },
  { value: "rejected", label: t("transaction.rejected") },
];

const methodOptions = (t: TFunction) => [
  { value: "", label: t("panel.common.all") },
  { value: "card", label: t("panel.common.cardTransfer") },
  { value: "crypto", label: t("panel.transactions.crypto") },
];

const STATUS_TONE: Record<string, "success" | "warning" | "danger" | "muted"> = {
  approved: "success",
  pending: "warning",
  rejected: "danger",
};

export default function AdminTransactionsPage() {
  const { t } = useTranslation();
  const [filters, setFilters] = useState({ status: "pending", method: "" });
  const [draft, setDraft] = useState({ status: "pending", method: "" });
  const [page, setPage] = useState(1);

  const query = usePanelQuery(["transactions", filters.status, filters.method, page], (auth) =>
    panelTransactionsApi.listTransactions({ ...auth, ...filters, page, limit: 25 })
  );

  const invalidate = [["transactions"], ["me"], ["dashboard"]];
  const approve = usePanelAction(panelTransactionsApi.approve, { invalidate });
  const reject = usePanelAction(panelTransactionsApi.reject, { invalidate });

  const columns: Column<PanelTransactionRow>[] = [
    { key: "id", header: "#", cell: (row) => <code className="ltr-field text-xs">{row.id}</code> },
    {
      key: "user",
      header: t("common.user"),
      cell: (row) => <code className="ltr-field text-xs">{row.user_id ?? "—"}</code>,
    },
    { key: "amount", header: t("panel.common.amount"), cell: (row) => formatToman(row.amount) },
    { key: "method", header: t("panel.transactions.method"), secondary: true, cell: (row) => row.method || "—" },
    {
      key: "created",
      header: t("panel.common.time"),
      secondary: true,
      cell: (row) => (
        <span className="text-xs text-muted">{row.created_at ? formatUnixDate(row.created_at) : "—"}</span>
      ),
    },
    {
      key: "receipt",
      header: t("panel.transactions.receipt"),
      secondary: true,
      cell: (row) =>
        row.receipt ? (
          <a href={row.receipt} target="_blank" rel="noopener noreferrer" className="text-xs text-primary hover:underline">
            {t("panel.transactions.view")}
          </a>
        ) : (
          "—"
        ),
    },
    {
      key: "status",
      header: t("panel.common.status"),
      cell: (row) => <Badge tone={STATUS_TONE[row.status || ""] || "muted"}>{row.status || "—"}</Badge>,
    },
    {
      key: "actions",
      header: t("panel.common.actions"),
      cell: (row) =>
        row.status === "pending" ? (
          <div className="flex flex-wrap gap-1.5">
            <ConfirmButton
              size="sm"
              message={t("panel.transactions.approveConfirm", { id: row.id, amount: formatToman(row.amount) })}
              onConfirm={() => approve.mutate({ tx_id: row.id })}
            >
              {t("panel.common.confirm")}
            </ConfirmButton>
            <ConfirmButton
              size="sm"
              variant="danger"
              message={t("panel.transactions.rejectConfirm", { id: row.id })}
              onConfirm={() => reject.mutate({ tx_id: row.id })}
            >
              {t("panel.transactions.reject")}
            </ConfirmButton>
          </div>
        ) : (
          <span className="text-xs text-muted">{t("panel.transactions.handled")}</span>
        ),
    },
  ];

  return (
    <>
      <PageHeader
        title={t("panel.common.transactions")}
        subtitle={
          query.data ? t("panel.transactions.pendingLabel", { count: formatNumber(query.data.pending_total) }) : undefined
        }
      />

      <Toolbar
        onSubmit={() => {
          setPage(1);
          setFilters(draft);
        }}
      >
        <div className="w-40">
          <SelectField
            label={t("panel.common.status")}
            options={statusOptions(t)}
            value={draft.status}
            onChange={(event) => setDraft((prev) => ({ ...prev, status: event.target.value }))}
          />
        </div>
        <div className="w-40">
          <SelectField
            label={t("panel.transactions.paymentMethod")}
            options={methodOptions(t)}
            value={draft.method}
            onChange={(event) => setDraft((prev) => ({ ...prev, method: event.target.value }))}
          />
        </div>
        <Button size="md" type="submit" variant="secondary">
          {t("panel.common.applyFilter")}
        </Button>
      </Toolbar>

      {query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : (
        <SectionCard title={t("panel.transactions.title")}>
          <DataTable
            columns={columns}
            rows={query.data?.transactions || []}
            rowKey={(row) => row.id}
            loading={query.isLoading}
            emptyTitle={t("panel.transactions.empty")}
          />
          <div className="mt-4">
            <Pagination page={page} totalPages={query.data?.meta.total_pages || 1} onChange={setPage} />
          </div>
        </SectionCard>
      )}
    </>
  );
}
