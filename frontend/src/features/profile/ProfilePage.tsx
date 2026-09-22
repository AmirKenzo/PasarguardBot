import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  CalendarDays,
  ChevronLeft,
  Copy,
  CreditCard,
  Download,
  HelpCircle,
  KeyRound,
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
import { AppVersion, Avatar, Badge, Button, Card, IconBadge, Modal, SkeletonCard } from "../../components/ui";
import { ErrorState } from "../../components/ui/EmptyState";
import { useToast } from "../../components/ui/Toast";
import { authApi } from "../../api/webapp";
import { useAuth } from "../../context/AuthContext";
import { useInstallPwa } from "../../hooks/useInstallPwa";
import { useIsAdmin } from "../../hooks/useIsAdmin";
import { formatExpiry, formatToman, formatUnixDate } from "../../lib/format";

type Tone = "primary" | "success" | "warning" | "danger" | "muted" | "accent";

export default function ProfilePage() {
  const { t } = useTranslation();
  const { user, setUser, sessionToken, initData, loading, refreshUser, clearSession, apiKeyLoginMode } = useAuth();
  const navigate = useNavigate();
  const { show } = useToast();
  const isAdmin = useIsAdmin();
  const { canInstall, install } = useInstallPwa();
  const [keyModalStep, setKeyModalStep] = useState<"confirm" | "reveal" | null>(null);
  const [generatedKey, setGeneratedKey] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

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

  async function handleGenerateApiKey() {
    setGenerating(true);
    try {
      const res = await authApi.generateApiKey({ session_token: sessionToken, init_data: initData });
      if (res.api_key) {
        // The backend just invalidated every session for this account (including
        // the one used for this very request), so it doesn't refetch the profile
        // over the network here -- that would fail and yank the reveal modal away
        // before the user can copy the key. Local state carries it instead; the
        // forced re-login happens once they close the modal below.
        setGeneratedKey(res.api_key);
        setKeyModalStep("reveal");
        if (user) {
          setUser({ ...user, has_api_key: true, api_key_created_at: res.created_at ?? null });
        }
      } else {
        show(res.error || t("profile.apiKey.genericError"), "error");
      }
    } catch (err) {
      show(err instanceof Error ? err.message : t("profile.apiKey.genericError"), "error");
    } finally {
      setGenerating(false);
    }
  }

  function handleGenerateClick() {
    if (user?.has_api_key) {
      setKeyModalStep("confirm");
    } else {
      void handleGenerateApiKey();
    }
  }

  async function handleCopyApiKey() {
    if (!generatedKey) return;
    try {
      await navigator.clipboard.writeText(generatedKey);
      show(t("profile.apiKey.copied"), "success");
    } catch {
      show(t("profile.apiKey.copyFailed"), "error");
    }
  }

  function closeConfirmModal() {
    setKeyModalStep(null);
  }

  function finishKeyReveal() {
    setKeyModalStep(null);
    setGeneratedKey(null);
    clearSession();
    navigate("/login", { replace: true });
    show(t("profile.apiKey.reloginNotice"), "info");
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

          {apiKeyLoginMode !== "none" && (
            <Card className="p-4">
              <div className="flex items-center gap-2.5">
                <IconBadge icon={KeyRound} tone="accent" size="sm" />
                <div className="min-w-0 flex-1">
                  <h2 className="font-semibold text-text">{t("profile.apiKey.title")}</h2>
                  <p className="text-xs text-muted">{t("profile.apiKey.description")}</p>
                </div>
              </div>

              {apiKeyLoginMode === "phone_verified" && !user.number ? (
                <p className="mt-3 text-xs text-warning">{t("profile.apiKey.phoneRequired")}</p>
              ) : (
                <>
                  {user.has_api_key && (
                    <p className="mt-3 text-xs text-muted">
                      {t("profile.apiKey.createdOn", {
                        date: user.api_key_created_at ? formatUnixDate(user.api_key_created_at) : "-",
                      })}
                    </p>
                  )}
                  <Button
                    variant="secondary"
                    fullWidth
                    className="mt-3"
                    loading={generating}
                    onClick={handleGenerateClick}
                  >
                    <KeyRound size={18} />
                    {user.has_api_key ? t("profile.apiKey.regenerate") : t("profile.apiKey.generate")}
                  </Button>
                </>
              )}
            </Card>
          )}

          {canInstall && (
            <Button variant="secondary" fullWidth onClick={() => void install()}>
              <Download size={18} />
              {t("profile.installApp")}
            </Button>
          )}

          <Button variant="danger" fullWidth onClick={() => void handleLogout()}>
            <LogOut size={18} />
            {t("profile.logout")}
          </Button>

          <div className="flex justify-center pt-1">
            <AppVersion />
          </div>
        </div>
      </div>

      <Modal
        open={keyModalStep === "confirm"}
        onClose={closeConfirmModal}
        title={t("profile.apiKey.confirmTitle")}
      >
        <p className="text-sm text-muted">{t("profile.apiKey.confirmBody")}</p>
        <div className="mt-4 flex gap-2">
          <Button variant="ghost" fullWidth onClick={closeConfirmModal}>
            {t("profile.apiKey.cancel")}
          </Button>
          <Button variant="danger" fullWidth loading={generating} onClick={() => void handleGenerateApiKey()}>
            {t("profile.apiKey.confirmRegenerate")}
          </Button>
        </div>
      </Modal>

      <Modal open={keyModalStep === "reveal"} onClose={finishKeyReveal} title={t("profile.apiKey.revealTitle")}>
        <p className="text-sm text-warning">{t("profile.apiKey.revealWarning")}</p>
        <div className="mt-3 flex items-center gap-2 rounded-lg bg-surface-2 p-3 ring-1 ring-border">
          <code className="min-w-0 flex-1 break-all text-left text-sm text-text" dir="ltr">
            {generatedKey}
          </code>
          <button
            onClick={() => void handleCopyApiKey()}
            className="shrink-0 rounded-md p-2 text-muted hover:bg-surface hover:text-text"
            aria-label={t("profile.apiKey.copy")}
          >
            <Copy size={16} />
          </button>
        </div>
        <p className="mt-3 text-xs text-muted">{t("profile.apiKey.reloginHint")}</p>
        <Button variant="secondary" fullWidth className="mt-4" onClick={finishKeyReveal}>
          {t("profile.apiKey.done")}
        </Button>
      </Modal>
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
