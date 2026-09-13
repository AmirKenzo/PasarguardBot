import { Link, useNavigate } from "react-router-dom";
import {
  CalendarDays,
  ChevronLeft,
  CreditCard,
  HelpCircle,
  LogOut,
  Percent,
  Phone,
  Users,
  Wallet,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { AppVersion, Avatar, Badge, Button, Card, IconBadge, SkeletonCard } from "../../components/ui";
import { ErrorState } from "../../components/ui/EmptyState";
import { useToast } from "../../components/ui/Toast";
import { authApi } from "../../api/webapp";
import { useAuth } from "../../context/AuthContext";
import { formatToman } from "../../lib/format";

type Tone = "primary" | "success" | "warning" | "danger" | "muted" | "accent";

export default function ProfilePage() {
  const { user, sessionToken, loading, refreshUser, clearSession } = useAuth();
  const navigate = useNavigate();
  const { show } = useToast();

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
      show("از حساب خارج شدید", "info");
    }
  }

  if (loading && !user) {
    return (
      <div>
        <PageHeader title="پروفایل" />
        <SkeletonCard />
      </div>
    );
  }

  if (!user) {
    return (
      <div>
        <PageHeader title="پروفایل" />
        <ErrorState message="خطا در بارگذاری پروفایل" onRetry={() => void refreshUser()} />
      </div>
    );
  }

  const tx = user.transactions;

  return (
    <div>
      <PageHeader title="پروفایل من" />

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
                    {user.first_name || user.username || "کاربر"}
                  </p>
                  <p className="truncate text-sm text-muted">@{user.username || "-"}</p>
                </div>
              </div>

              {user.discount && (
                <div className="mt-4 rounded-lg bg-surface-2 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <IconBadge icon={Percent} tone="primary" size="sm" />
                    <Badge tone="primary">{user.discount.percent}% تخفیف</Badge>
                    <span className="text-sm text-text">کد: {user.discount.code}</span>
                  </div>
                  <p className="mt-1 text-xs text-muted">
                    {user.discount.usage} • انقضا: {user.discount.expiration}
                  </p>
                </div>
              )}
            </div>
          </Card>

          <Card className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-4 md:grid-cols-2">
            <InfoTile icon={Wallet} label="موجودی" value={formatToman(user.amount)} tone="primary" />
            <InfoTile icon={Users} label="دعوت" value={String(user.invite ?? 0)} tone="accent" />
            <InfoTile icon={CalendarDays} label="تاریخ عضویت" value={user.join_date ?? "-"} tone="success" />
            <InfoTile icon={Phone} label="شماره" value={user.number ?? "-"} tone="warning" />
          </Card>
        </div>

        <div className="mt-4 space-y-4 md:col-span-2 md:mt-0">
          <Card className="p-4">
            <h2 className="mb-3 font-semibold text-text">آمار تراکنش‌ها</h2>
            <div className="grid grid-cols-2 gap-2">
              <TxStat icon={CreditCard} label="دستی" count={tx.manual.count} total={tx.manual.total_amount} />
              <TxStat icon={Wallet} label="ارزی" count={tx.crypto.count} total={tx.crypto.total_amount} />
            </div>
          </Card>

          <Card className="divide-y divide-border overflow-hidden">
            <ProfileLink to="/help" icon={HelpCircle} label="راهنما" />
          </Card>

          <Button variant="danger" fullWidth onClick={() => void handleLogout()}>
            <LogOut size={18} />
            خروج از حساب
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
  return (
    <div className="flex items-center gap-2.5 rounded-lg bg-surface-2 px-3 py-2.5 ring-1 ring-border">
      <IconBadge icon={Icon} tone="muted" size="sm" />
      <div className="min-w-0">
        <span className="block text-xs text-muted">{label}</span>
        <p className="truncate text-sm font-medium text-text">{count} تراکنش</p>
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
