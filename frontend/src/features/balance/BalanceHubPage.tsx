import { Link } from "react-router-dom";
import { ChevronLeft, CreditCard, DollarSign, History, Star } from "lucide-react";
import { useTranslation } from "react-i18next";
import { PageHeader } from "../../components/layout/PageHeader";
import { Card, EmptyState, IconBadge } from "../../components/ui";
import { ErrorState } from "../../components/ui/EmptyState";
import { Skeleton } from "../../components/ui/Skeleton";
import { useAuth } from "../../context/AuthContext";
import { formatToman } from "../../lib/format";
import { useBalanceMethodsQuery } from "../../queries/useBalance";

export default function BalanceHubPage() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const { data: methods, isLoading, isError, refetch } = useBalanceMethodsQuery();

  return (
    <div>
      <PageHeader
        title={t("balanceHub.title")}
        subtitle={user ? t("balanceHub.balance", { amount: formatToman(user.amount) }) : undefined}
        action={
          <Link
            to="/balance/transactions"
            className="flex items-center gap-1 rounded-md border border-border px-3 py-1.5 text-xs text-text"
          >
            <History size={14} />
            {t("balanceHub.transactions")}
          </Link>
        }
      />

      {isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : isError ? (
        <ErrorState message={t("balanceHub.loadError")} onRetry={() => void refetch()} />
      ) : !methods ? null : !hasAnyMethod(methods) ? (
        <EmptyState title={t("balanceHub.noMethodActive")} description={t("balanceHub.noMethodActiveDesc")} />
      ) : (
        <div className="space-y-3">
          {methods.cart_sta && (
            <MethodLink
              to="/balance/stars"
              icon={Star}
              title={t("balanceHub.starsPay")}
              description={`${t("balanceHub.starsPayDesc")}${bonusText(methods.stars_bonus_percent, t)}`}
            />
          )}
          {methods.pay_mode && (
            <MethodLink
              to="/balance/manual"
              icon={CreditCard}
              title={t("balanceHub.manualCard")}
              description={`${t("balanceHub.manualCardDesc")}${bonusText(methods.manual_bonus_percent, t)}`}
            />
          )}
          {methods.arz_mode && (
            <MethodLink
              to="/balance/crypto"
              icon={DollarSign}
              title={t("balanceHub.cryptoPay")}
              description={`TRX, USDT, TON${bonusText(methods.crypto_bonus_percent, t)}`}
            />
          )}
        </div>
      )}
    </div>
  );
}

function hasAnyMethod(methods: NonNullable<ReturnType<typeof useBalanceMethodsQuery>["data"]>) {
  return methods.pay_mode || methods.arz_mode || methods.cart_sta;
}

function bonusText(percent: number, t: (key: string, opts?: Record<string, unknown>) => string) {
  return percent ? t("balanceHub.bonus", { percent }) : "";
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
