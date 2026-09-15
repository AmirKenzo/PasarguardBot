import { Link, useNavigate } from "react-router-dom";
import {
  CalendarDays,
  ChevronLeft,
  CreditCard,
  HelpCircle,
  LogOut,
  Percent,
  Phone,
  ShieldCheck,
  Users,
  Wallet,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { PageHeader } from "../../components/layout/PageHeader";
import { AppVersion, Avatar, Badge, Button, Card, IconBadge, SkeletonCard } from "../../components/ui";
import { ErrorState } from "../../components/ui/EmptyState";
import { useToast } from "../../components/ui/Toast";
import { authApi } from "../../api/webapp";
import { useAuth } from "../../context/AuthContext";
import { useIsAdmin } from "../../hooks/useIsAdmin";
import { formatExpiry, formatToman, formatUnixDate } from "../../lib/format";

type Tone = "primary" | "success" | "warning" | "danger" | "muted" | "accent";

export default function ProfilePage() {
  const { t } = useTranslation();
  const { user, sessionToken, loading, refreshUser, clearSession } = useAuth();
  const navigate = useNavigate();
  const { show } = useToast();
  const isAdmin = useIsAdmin();

  async function handleLogout() {
    try {
      if (sessionToken) {
        await authApi.logout({ session_token: sessionToken });
      }
    } catch {
      // still clear local session
    } finally {
      clearSession();
      navigate("/login", { replace: true });
      show(t("profile.loggedOut"), "info");
    }
  }

  if (loading && !user) {
    return (
      <div>
        <PageHeader title={t("profile.title")} />
        <SkeletonCard />
      </div>
    );
  }

  if (!user) {
    return (
      <div>
        <PageHeader title={t("profile.title")} />
        <ErrorState message={t("profile.loadError")} onRetry={() => void refreshUser()} />
      </div>
    );
  }

  const tx = user.transactions;

  return (
    <div>
      <PageHeader title={t("profile.title")} />

      <div className="md:grid md:grid-cols-5 md:items-start md:gap-4">
        <div className="space-y-4 md:col-span-3">
          <Card className="overflow-hidden">
            <div className="h-16 bg-gradient-to-l from-primary/20 to-accent/20" />
            <div className="px-4 pb-4">
              <div className="-mt-8 flex items-end gap-3">
                <Avatar
                  src={user.photo_url}
                  name={user.first_name || user.username}
                  size={72}
                  className="shrink-0 ring-4 ring-surface"
                />
                <div className="min-w-0 flex-1 pb-1">
                  <p className="truncate text-lg font-semibold text-text">
                    {user.first_name || user.username || t("common.user")}
                  </p>
                  <p className="truncate text-sm text-muted">@{user.username || "-"}</p>
                </div>
              </div>

              {user.discount && (
                <div className="mt-4 rounded-lg bg-surface-2 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <IconBadge icon={Percent} tone="primary" size="sm" />
                    <Badge tone="primary">{t("profile.discountPercent", { percent: user.discount.percent })}</Badge>
                    <span className="text-sm text-text">
                      {t("profile.code")}: {user.discount.code}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-muted">
                    {t("profile.usageOf", { used: user.discount.times_used, limit: user.discount.usage_limit })} •{" "}
                    {t("profile.expiry")}: {formatExpiry(user.discount.expiration_timestamp).date}
                  </p>
                </div>
              )}
            </div>
          </Card>

          <Card className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-4 md:grid-cols-2">
            <InfoTile icon={Wallet} label={t("profile.balance")} value={formatToman(user.amount)} tone="primary" />
            <InfoTile icon={Users} label={t("profile.invites")} value={String(user.invite ?? 0)} tone="accent" />
            <InfoTile
              icon={CalendarDays}
              label={t("profile.joinDate")}
              value={user.join_date ? formatUnixDate(user.join_date) : "-"}
              tone="success"
            />
            <InfoTile icon={Phone} label={t("profile.phoneNumber")} value={user.number ?? "-"} tone="warning" />
          </Card>
        </div>

        <div className="mt-4 space-y-4 md:col-span-2 md:mt-0">
          <Card className="p-4">
            <h2 className="mb-3 font-semibold text-text">{t("profile.transactionStats")}</h2>
            <div className="grid grid-cols-2 gap-2">
              <TxStat icon={CreditCard} label={t("profile.manual")} count={tx.manual.count} total={tx.manual.total_amount} />
              <TxStat icon={Wallet} label={t("profile.crypto")} count={tx.crypto.count} total={tx.crypto.total_amount} />
            </div>
          </Card>

          <Card className="divide-y divide-border overflow-hidden">
            {isAdmin && <ProfileLink to="/panel" icon={ShieldCheck} label={t("profile.adminPanel")} />}
            <ProfileLink to="/help" icon={HelpCircle} label={t("profile.help")} />
          </Card>

          <Button variant="danger" fullWidth onClick={() => void handleLogout()}>
            <LogOut size={18} />
            {t("profile.logout")}
          </Button>

          <div className="flex justify-center pt-1">
            <AppVersion />
          </div>
        </div>
      </div>
    </div>
  );
}

function InfoTile({
  icon: Icon,
  label,
  value,
  tone = "primary",
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  tone?: Tone;
}) {
  return (
    <div className="flex items-center gap-2.5 rounded-lg bg-surface-2 px-3 py-2.5 ring-1 ring-border">
      <IconBadge icon={Icon} tone={tone} size="sm" />
      <div className="min-w-0">
        <span className="block text-xs text-muted">{label}</span>
        <p className="truncate text-sm font-medium text-text">{value}</p>
      </div>
    </div>
  );
}

function TxStat({
  icon: Icon,
  label,
  count,
  total,
}: {
  icon: LucideIcon;
  label: string;
  count: number;
  total: number;
}) {
  const { t } = useTranslation();
  return (
    <div className="flex items-center gap-2.5 rounded-lg bg-surface-2 px-3 py-2.5 ring-1 ring-border">
      <IconBadge icon={Icon} tone="muted" size="sm" />
      <div className="min-w-0">
        <span className="block text-xs text-muted">{label}</span>
        <p className="truncate text-sm font-medium text-text">{t("profile.transactionsCount", { count })}</p>
        <p className="truncate text-xs text-muted">{formatToman(total)}</p>
      </div>
    </div>
  );
}

function ProfileLink({ to, icon: Icon, label }: { to: string; icon: LucideIcon; label: string }) {
  return (
    <Link
      to={to}
      className="flex items-center gap-3 px-4 py-3 text-sm text-text transition-colors hover:bg-surface-2"
    >
      <IconBadge icon={Icon} tone="primary" size="sm" />
      <span className="flex-1">{label}</span>
      <ChevronLeft size={16} className="text-muted" />
    </Link>
  );
}
