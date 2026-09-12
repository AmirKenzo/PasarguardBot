import { Link, useNavigate } from "react-router-dom";
import {
  ChevronLeft,
  HelpCircle,
  KeyRound,
  LogOut,
  UserPlus,
} from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Avatar, Badge, Button, Card, IconBadge, SkeletonCard } from "../../components/ui";
import { ErrorState } from "../../components/ui/EmptyState";
import { useToast } from "../../components/ui/Toast";
import { authApi } from "../../api/webapp";
import { useAuth } from "../../context/AuthContext";
import { formatToman } from "../../lib/format";

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

      <Card className="mb-4 p-4">
        <div className="mb-4 flex items-center gap-3">
          <Avatar src={user.photo_url} name={user.first_name || user.username} size={64} />
          <div className="min-w-0 flex-1">
            <p className="text-lg font-semibold text-text">
              {user.first_name || user.username || "کاربر"}
            </p>
            <p className="text-sm text-muted">@{user.username || "-"}</p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
          <InfoTile label="موجودی" value={formatToman(user.amount)} />
          <InfoTile label="دعوت" value={String(user.invite ?? 0)} />
          <InfoTile label="تاریخ عضویت" value={user.join_date ?? "-"} />
          <InfoTile label="شماره" value={user.number ?? "-"} />
        </div>

        {user.discount && (
          <div className="mt-4 rounded-md bg-surface-2 p-3">
            <div className="flex items-center gap-2">
              <Badge tone="primary">{user.discount.percent}%</Badge>
              <span className="text-sm text-text">کد: {user.discount.code}</span>
            </div>
            <p className="mt-1 text-xs text-muted">
              {user.discount.usage} • انقضا: {user.discount.expiration}
            </p>
          </div>
        )}
      </Card>

      <Card className="mb-4 p-4">
        <h2 className="mb-3 font-semibold text-text">آمار تراکنش‌ها</h2>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <TxStat label="دستی" count={tx.manual.count} total={tx.manual.total_amount} />
          <TxStat label="ارزی" count={tx.crypto.count} total={tx.crypto.total_amount} />
        </div>
      </Card>

      <Card className="mb-4 divide-y divide-border overflow-hidden">
        <ProfileLink to="/profile/create-account" icon={UserPlus} label="ساخت اکانت وب" />
        <ProfileLink to="/profile/change-password" icon={KeyRound} label="تغییر رمز عبور" />
        <ProfileLink to="/help" icon={HelpCircle} label="راهنما" />
      </Card>

      <Button variant="danger" fullWidth onClick={() => void handleLogout()}>
        <LogOut size={18} />
        خروج از حساب
      </Button>
    </div>
  );
}

function InfoTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-surface-2 px-3 py-2 ring-1 ring-border/60">
      <span className="block text-xs text-muted">{label}</span>
      <p className="truncate font-medium text-text">{value}</p>
    </div>
  );
}

function TxStat({ label, count, total }: { label: string; count: number; total: number }) {
  return (
    <div className="rounded-lg bg-surface-2 px-3 py-2 ring-1 ring-border/60">
      <span className="block text-xs text-muted">{label}</span>
      <p className="font-medium text-text">{count} تراکنش</p>
      <p className="text-xs text-muted">{formatToman(total)}</p>
    </div>
  );
}

function ProfileLink({
  to,
  icon: Icon,
  label,
}: {
  to: string;
  icon: typeof UserPlus;
  label: string;
}) {
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
