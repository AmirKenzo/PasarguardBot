import { useState } from "react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge, Card, EmptyState, IconBadge, Pagination } from "../../components/ui";
import { ErrorState } from "../../components/ui/EmptyState";
import { Skeleton } from "../../components/ui/Skeleton";
import { formatToman, formatUnixDate } from "../../lib/format";
import { transactionIcon } from "../../lib/transactionIcon";
import { useTransactionsQuery } from "../../queries/useTransactions";

function txStatusTone(status: string): "success" | "warning" | "danger" | "muted" {
  if (status === "approved" || status === "Paid") return "success";
  if (status === "pending" || status === "Pending") return "warning";
  if (status === "rejected" || status === "Expired") return "danger";
  return "muted";
}

function txStatusLabel(status: string): string {
  if (status === "approved" || status === "Paid") return "تایید شده";
  if (status === "pending" || status === "Pending") return "در انتظار";
  if (status === "rejected" || status === "Expired") return "رد/منقضی";
  return status;
}

export default function TransactionsPage() {
  const [page, setPage] = useState(1);
  const { data, isLoading, isError, refetch } = useTransactionsQuery(page, 15);

  return (
    <div>
      <PageHeader title="تراکنش‌ها" back="/balance" />

      {isLoading ? (
        <Skeleton className="h-48 w-full" />
      ) : isError ? (
        <ErrorState message="خطا در بارگذاری تراکنش‌ها" onRetry={() => void refetch()} />
      ) : !data?.transactions.length ? (
        <EmptyState title="تراکنشی یافت نشد" description="هنوز تراکنشی ثبت نشده است." />
      ) : (
        <>
          <div className="space-y-2">
            {data.transactions.map((tx) => (
              <Card key={tx.id} className="flex items-center gap-3 px-3 py-3">
                <IconBadge icon={transactionIcon(tx.emoji)} tone={txStatusTone(tx.status)} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm text-text">{tx.type}</p>
                  <p className="text-xs text-muted">{formatUnixDate(tx.created_at)}</p>
                </div>
                <div className="text-left">
                  <p className="text-sm text-text">{formatToman(tx.amount)}</p>
                  <Badge tone={txStatusTone(tx.status)}>{txStatusLabel(tx.status)}</Badge>
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
