import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowLeft, ChevronLeft, Gift, ShoppingBag, Signal, UserPlus, Wallet } from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Avatar, Badge, Card, IconBadge, Skeleton, SkeletonCard } from "../../components/ui";
import { ErrorState } from "../../components/ui/EmptyState";
import { useAuth } from "../../context/AuthContext";
import { formatToman, formatUnixDate } from "../../lib/format";
import { transactionIcon } from "../../lib/transactionIcon";
import { useRecentTransactionsQuery } from "../../queries/useTransactions";

const QUICK_ACTIONS = [
  { to: "/services", label: "سرویس‌های من", icon: Signal },
  { to: "/buy", label: "خرید سرویس", icon: ShoppingBag },
  { to: "/balance", label: "افزایش موجودی", icon: Wallet },
];

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

export default function DashboardPage() {
  const { user, loading, refreshUser } = useAuth();
  const { data: txData, isLoading: txLoading } = useRecentTransactionsQuery(5);

  if (loading && !user) {
    return (
      <div>
        <PageHeader title="داشبورد" />
        <SkeletonCard />
      </div>
    );
  }

  if (!user) {
    return (
      <div>
        <PageHeader title="داشبورد" />
        <ErrorState message="خطا در بارگذاری پروفایل" onRetry={() => void refreshUser()} />
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="داشبورد" subtitle={`سلام ${user.first_name || user.username || "کاربر"}`} />

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
        className="relative mb-4 overflow-hidden rounded-lg bg-gradient-to-br from-primary to-primary-strong p-5 text-primary-text shadow-md shadow-primary/25"
      >
        <div className="pointer-events-none absolute -left-8 -top-14 h-36 w-36 rounded-full bg-white/10 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-14 -right-6 h-32 w-32 rounded-full bg-white/10 blur-3xl" />

        <div className="relative flex items-center gap-3">
          <Avatar
            src={user.photo_url}
            name={user.first_name || user.username}
            size={44}
            className="ring-2 ring-white/30"
          />
          <div className="min-w-0 flex-1">
            <p className="truncate font-semibold">{user.first_name || user.username || "کاربر"}</p>
            <p className="truncate text-xs text-primary-text/70">@{user.username || "-"}</p>
          </div>
          {user.discount && (
            <span className="flex shrink-0 items-center gap-1 rounded-full bg-white/15 px-2.5 py-1 text-xs font-medium">
              <Gift size={12} />
              {user.discount.percent}%
            </span>
          )}
        </div>

        <div className="relative mt-5 flex items-end justify-between gap-3">
          <div>
            <p className="text-xs text-primary-text/70">موجودی کیف پول</p>
            <p className="mt-1 text-2xl font-extrabold tracking-tight" dir="ltr">
              {formatToman(user.amount)}
            </p>
          </div>
          <Link
            to="/balance"
            className="flex items-center gap-1 rounded-md bg-white/15 px-3 py-2 text-xs font-medium transition-colors hover:bg-white/25"
          >
            افزایش
            <ChevronLeft size={14} />
          </Link>
        </div>

        <div className="relative mt-3 flex items-center gap-1.5 text-xs text-primary-text/70">
          <UserPlus size={12} />
          {user.invite ?? 0} دعوت موفق
        </div>
      </motion.div>

      <div className="mb-6 grid grid-cols-3 gap-2.5">
        {QUICK_ACTIONS.map((action) => (
          <Link key={action.to} to={action.to} className="block">
            <Card interactive className="flex items-center gap-2.5 p-3">
              <IconBadge icon={action.icon} tone="primary" size="sm" />
              <span className="truncate text-xs font-medium text-text">{action.label}</span>
            </Card>
          </Link>
        ))}
      </div>

      <Card className="p-4">
        <div className="mb-3 flex items-center justify-between gap-2">
          <h2 className="font-semibold text-text">فعالیت اخیر</h2>
          <Link to="/balance/transactions" className="flex items-center gap-1 text-xs text-primary">
            همه تراکنش‌ها
            <ArrowLeft size={14} />
          </Link>
        </div>
        {txLoading ? (
          <Skeleton className="h-20 w-full" />
        ) : !txData?.transactions?.length ? (
          <p className="text-sm text-muted">تراکنشی یافت نشد.</p>
        ) : (
          <div className="space-y-2">
            {txData.transactions.map((tx) => (
              <div
                key={tx.id}
                className="flex items-center gap-3 rounded-md bg-surface-2 px-3 py-2 shadow-sm ring-1 ring-border/60"
              >
                <IconBadge icon={transactionIcon(tx.emoji)} tone={txStatusTone(tx.status)} size="sm" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm text-text">{tx.type}</p>
                  <p className="text-xs text-muted">{formatUnixDate(tx.created_at)}</p>
                </div>
                <div className="text-left">
                  <p className="text-sm text-text">{formatToman(tx.amount)}</p>
                  <Badge tone={txStatusTone(tx.status)}>{txStatusLabel(tx.status)}</Badge>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
