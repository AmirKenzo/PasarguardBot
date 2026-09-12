import { Link } from "react-router-dom";
import { ChevronLeft, CreditCard, DollarSign, History } from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Card, EmptyState, IconBadge } from "../../components/ui";
import { ErrorState } from "../../components/ui/EmptyState";
import { Skeleton } from "../../components/ui/Skeleton";
import { useAuth } from "../../context/AuthContext";
import { formatToman } from "../../lib/format";
import { useBalanceMethodsQuery } from "../../queries/useBalance";

export default function BalanceHubPage() {
  const { user } = useAuth();
  const { data: methods, isLoading, isError, refetch } = useBalanceMethodsQuery();

  return (
    <div>
      <PageHeader
        title="کیف پول"
        subtitle={user ? `موجودی: ${formatToman(user.amount)}` : undefined}
        action={
          <Link
            to="/balance/transactions"
            className="flex items-center gap-1 rounded-md border border-border px-3 py-1.5 text-xs text-text"
          >
            <History size={14} />
            تراکنش‌ها
          </Link>
        }
      />

      {isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : isError ? (
        <ErrorState message="خطا در بارگذاری روش‌های پرداخت" onRetry={() => void refetch()} />
      ) : !methods ? null : !hasAnyMethod(methods) ? (
        <EmptyState title="روش شارژ فعال نیست" description="در حال حاضر امکان افزایش موجودی وجود ندارد." />
      ) : (
        <div className="space-y-3">
          {methods.pay_mode && (
            <MethodLink
              to="/balance/manual"
              icon={CreditCard}
              title="کارت به کارت"
              description={`رسید در همین وب‌اپ ارسال می‌شود${bonusText(methods.manual_bonus_percent)}`}
            />
          )}
          {methods.arz_mode && (
            <MethodLink
              to="/balance/crypto"
              icon={DollarSign}
              title="پرداخت ارزی"
              description={`TRX, USDT, TON${bonusText(methods.crypto_bonus_percent)}`}
            />
          )}
        </div>
      )}
    </div>
  );
}

function hasAnyMethod(methods: NonNullable<ReturnType<typeof useBalanceMethodsQuery>["data"]>) {
  return methods.pay_mode || methods.arz_mode;
}

function bonusText(percent: number) {
  return percent ? ` • بونوس ${percent}%` : "";
}

function MethodLink({
  to,
  icon: Icon,
  title,
  description,
}: {
  to: string;
  icon: typeof CreditCard;
  title: string;
  description: string;
}) {
  return (
    <Link to={to} className="block">
      <Card interactive className="flex items-center gap-3 p-4">
        <IconBadge icon={Icon} tone="primary" size="lg" />
        <div className="min-w-0 flex-1">
          <p className="font-medium text-text">{title}</p>
          <p className="text-xs text-muted">{description}</p>
        </div>
        <ChevronLeft size={18} className="text-muted" />
      </Card>
    </Link>
  );
}
