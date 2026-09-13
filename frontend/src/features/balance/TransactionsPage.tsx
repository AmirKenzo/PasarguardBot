import { useState } from "react";
import { useTranslation } from "react-i18next";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge, Card, EmptyState, IconBadge, Pagination } from "../../components/ui";
import { ErrorState } from "../../components/ui/EmptyState";
import { Skeleton } from "../../components/ui/Skeleton";
import { formatToman, formatUnixDate } from "../../lib/format";
import { transactionTypeLabel } from "../../lib/serviceHelpers";
import { transactionIcon } from "../../lib/transactionIcon";
import { useTransactionsQuery } from "../../queries/useTransactions";

function txStatusTone(status: string): "success" | "warning" | "danger" | "muted" {
  if (status === "approved" || status === "Paid") return "success";
  if (status === "pending" || status === "Pending") return "warning";
  if (status === "rejected" || status === "Expired") return "danger";
  return "muted";
}

function txStatusLabel(status: string, t: (key: string) => string): string {
  if (status === "approved" || status === "Paid") return t("transaction.approved");
  if (status === "pending" || status === "Pending") return t("transaction.pending");
  if (status === "rejected" || status === "Expired") return t("transaction.expired");
  return status;
}

export default function TransactionsPage() {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const { data, isLoading, isError, refetch } = useTransactionsQuery(page, 15);

  return (
    <div>
      <PageHeader title={t("transactions.title")} back="/balance" />

      {isLoading ? (
        <Skeleton className="h-48 w-full" />
      ) : isError ? (
        <ErrorState message={t("transactions.loadError")} onRetry={() => void refetch()} />
      ) : !data?.transactions.length ? (
        <EmptyState title={t("transactions.notFound")} description={t("transactions.notFoundDesc")} />
      ) : (
        <>
          <div className="space-y-2">
            {data.transactions.map((tx) => (
              <Card key={tx.id} className="flex items-center gap-3 px-3 py-3">
                <IconBadge icon={transactionIcon(tx.emoji)} tone={txStatusTone(tx.status)} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm text-text">{transactionTypeLabel(tx.type_key, tx.currency)}</p>
                  <p className="text-xs text-muted">{formatUnixDate(tx.created_at)}</p>
                </div>
                <div className="text-left">
                  <p className="text-sm text-text">{formatToman(tx.amount)}</p>
                  <Badge tone={txStatusTone(tx.status)}>{txStatusLabel(tx.status, t)}</Badge>
                </div>
              </Card>
            ))}
          </div>
          <Pagination page={data.page} totalPages={data.total_pages} onChange={setPage} />
        </>
      )}
    </div>
  );
}
