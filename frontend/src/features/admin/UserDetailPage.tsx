import { useState } from "react";
import { useParams } from "react-router-dom";
import { Ban, MessageSquare, Phone, Server, Wallet } from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge, Button, ErrorState, IconBadge, Input, Skeleton } from "../../components/ui";
import { formatBytes, formatExpiry, formatNumber, formatToman, formatUnixDate } from "../../lib/format";
import { panelUsersApi } from "../../api/panel";
import type { UserState } from "../../types/panel";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { ConfirmButton, FormModal, SectionCard, StatTile, Toggle } from "./components";
import { useTranslation } from "react-i18next";

const TX_TONE: Record<string, "success" | "warning" | "danger" | "muted"> = {
  approved: "success",
  pending: "warning",
  rejected: "danger",
};

const STATE_TONE: Record<UserState, "success" | "warning" | "danger" | "default"> = {
  active: "success",
  banned: "danger",
  blocked_bot: "warning",
  deleted: "default",
};

export default function AdminUserDetailPage() {
  const { t } = useTranslation();
  const params = useParams();
  const userId = Number(params.userId);

  const [balanceOpen, setBalanceOpen] = useState(false);
  const [messageOpen, setMessageOpen] = useState(false);
  const [phoneOpen, setPhoneOpen] = useState(false);

  const query = usePanelQuery(
    ["user", userId],
    (auth) => panelUsersApi.getUser({ ...auth, user_id: userId }),
    { enabled: Number.isFinite(userId) }
  );

  const invalidate = [["user", userId], ["users"]];
  const block = usePanelAction(panelUsersApi.setBlocked, { invalidate });

  if (query.isLoading) {
    return (
      <>
        <PageHeader title={t("common.user")} back="/panel/users" />
        <Skeleton className="h-64 w-full rounded-lg" />
      </>
    );
  }

  if (query.isError || !query.data?.user) {
    return (
      <>
        <PageHeader title={t("common.user")} back="/panel/users" />
        <ErrorState
          message={query.error?.message || t("panel.userDetail.notFound")}
          onRetry={() => void query.refetch()}
        />
      </>
    );
  }

  const { user, services, transactions, referrals } = query.data;
  const stateLabels: Record<UserState, string> = {
    active: t("panel.common.active"),
    banned: t("panel.users.stateBanned"),
    blocked_bot: t("panel.users.stateBlockedBot"),
    deleted: t("panel.users.stateDeleted"),
  };
  // Only an admin ban is reversible here — BlockedBot/deleted self-clear
  // once the user interacts with the bot again, an admin action can't fix either.
  const canToggleBlock = user.state === "active" || user.state === "banned";

  return (
    <>
      <PageHeader
        title={t("panel.userDetail.title", { id: user.id })}
        subtitle={user.number || t("panel.userDetail.noPhone")}
        back="/panel/users"
        action={
          <div className="flex flex-wrap gap-1.5">
            <Button size="sm" variant="secondary" className="!h-9 !w-9 !px-0" title={t("panel.users.balance")} onClick={() => setBalanceOpen(true)}>
              <Wallet size={15} />
            </Button>
            <Button size="sm" variant="secondary" className="!h-9 !w-9 !px-0" title={t("panel.userDetail.phoneNumber")} onClick={() => setPhoneOpen(true)}>
              <Phone size={15} />
            </Button>
            <Button size="sm" variant="secondary" className="!h-9 !w-9 !px-0" title={t("panel.userDetail.message")} onClick={() => setMessageOpen(true)}>
              <MessageSquare size={15} />
            </Button>
            {canToggleBlock && (
              <ConfirmButton
                size="sm"
                variant={user.state === "banned" ? "secondary" : "danger"}
                className="!h-9 !w-9 !px-0"
                title={user.state === "banned" ? t("panel.common.unblock") : t("panel.userDetail.block")}
                message={
                  user.state === "banned"
                    ? t("panel.userDetail.unblockConfirm", { id: user.id })
                    : t("panel.userDetail.blockConfirm", { id: user.id })
                }
                onConfirm={() => block.mutate({ user_id: user.id, blocked: user.state !== "banned", notify: true })}
              >
                <Ban size={15} />
              </ConfirmButton>
            )}
          </div>
        }
      />

      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        <StatTile dense label={t("panel.userDetail.walletBalance")} value={formatToman(user.balance)} tone="primary" />
        <StatTile dense label={t("panel.common.services")} value={formatNumber(user.services)} />
        <StatTile dense label={t("panel.userDetail.successfulInvites")} value={formatNumber(referrals)} />
        <StatTile
          dense
          label={t("panel.common.status")}
          value={stateLabels[user.state]}
          hint={user.state === "blocked_bot" ? t("panel.users.blockedBotHint") : user.state === "deleted" ? t("panel.users.deletedHint") : undefined}
          tone={STATE_TONE[user.state]}
        />
      </div>

      <SectionCard title={t("panel.userDetail.profile")}>
        <dl className="-my-1 divide-y divide-border/60 text-xs">
          <Detail label={t("panel.userDetail.numericId")} value={user.id} ltr />
          <Detail label={t("panel.userDetail.phoneNumber")} value={user.number || t("panel.userDetail.notSet")} ltr={Boolean(user.number)} />
          <Detail label={t("panel.userDetail.joinedAt")} value={user.joined_at ? formatUnixDate(user.joined_at) : "—"} />
        </dl>
      </SectionCard>

      <SectionCard title={t("panel.userDetail.servicesTitle", { count: formatNumber(services.length) })}>
        {services.length ? (
          <div className="-mt-1 divide-y divide-border/60">
            {services.map((service) => {
              const expiry = formatExpiry(service.expiration_time);
              return (
                <div key={service.code} className="flex flex-wrap items-center gap-2.5 py-2.5 first:pt-0 last:pb-0">
                  <IconBadge icon={Server} tone="muted" size="sm" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5 text-xs font-semibold text-text">
                      {service.username || "—"}
                      <code className="ltr-field text-[11px] font-normal text-muted">#{service.code}</code>
                    </div>
                    <div className="text-[11px] text-muted">
                      {service.panel || "—"} · {service.package_size ? formatBytes(service.package_size, 1) : t("common.unlimited")}
                    </div>
                  </div>
                  <div className="text-[11px] text-muted">{expiry.remaining}</div>
                  {!service.enable ? (
                    <Badge tone="warning">{t("panel.common.inactive")}</Badge>
                  ) : service.is_test ? (
                    <Badge tone="primary">{t("panel.services.trial")}</Badge>
                  ) : (
                    <Badge tone="success">{t("panel.common.active")}</Badge>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <p className="py-6 text-center text-sm text-muted">{t("panel.userDetail.noServices")}</p>
        )}
      </SectionCard>

      <SectionCard title={t("panel.userDetail.recentTransactions")}>
        {transactions.length ? (
          <div className="-mt-1 divide-y divide-border/60">
            {transactions.map((tx) => (
              <div key={tx.id} className="flex flex-wrap items-center gap-2.5 py-2.5 first:pt-0 last:pb-0">
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-semibold text-text">
                    {formatToman(tx.amount)}
                    <code className="ltr-field ms-1.5 text-[11px] font-normal text-muted">#{tx.id}</code>
                  </div>
                  <div className="text-[11px] text-muted">{tx.created_at ? formatUnixDate(tx.created_at) : "—"}</div>
                </div>
                <Badge tone={TX_TONE[tx.status || ""] || "muted"}>{tx.status || "—"}</Badge>
              </div>
            ))}
          </div>
        ) : (
          <p className="py-6 text-center text-sm text-muted">{t("panel.userDetail.noTransactions")}</p>
        )}
      </SectionCard>

      <BalanceDialog
        open={balanceOpen}
        onClose={() => setBalanceOpen(false)}
        userId={user.id}
        balance={user.balance}
        invalidate={invalidate}
      />
      <PhoneDialog
        open={phoneOpen}
        onClose={() => setPhoneOpen(false)}
        userId={user.id}
        number={user.number}
        invalidate={invalidate}
      />
      <MessageDialog open={messageOpen} onClose={() => setMessageOpen(false)} userId={user.id} />
    </>
  );
}

/** Records the phone number the browser login checks against.
 *
 *  Telegram never hands the bot a phone number on its own, so on a fresh
 *  install nobody has one — including the admin, who then cannot sign in to
 *  the panel outside Telegram. This is the bot's own confirm-phone action,
 *  reachable from the panel and normalising the number the same way. */
function PhoneDialog({
  open,
  onClose,
  userId,
  number,
  invalidate,
}: {
  open: boolean;
  onClose: () => void;
  userId: number;
  number?: string | null;
  invalidate: (string | number)[][];
}) {
  const { t } = useTranslation();
  const [phone, setPhone] = useState(number || "");
  const save = usePanelAction(panelUsersApi.setPhone, { invalidate });

  return (
    <FormModal open={open} onClose={onClose} title={t("panel.userDetail.phoneTitle", { id: userId })}>
      <div className="space-y-4">
        <Input
          label={t("panel.userDetail.phoneNumber")}
          inputMode="tel"
          dir="ltr"
          value={phone}
          onChange={(event) => setPhone(event.target.value)}
          placeholder={t("panel.userDetail.phonePlaceholder")}
        />
        <p className="text-xs text-muted">{t("panel.userDetail.phoneHint")}</p>
        <div className="flex justify-end gap-2">
          <Button size="sm" variant="ghost" onClick={onClose}>
            {t("panel.common.dismiss")}
          </Button>
          <Button
            size="sm"
            loading={save.isPending}
            onClick={() =>
              save.mutate({ user_id: userId, phone: phone.trim() }, { onSuccess: onClose })
            }
          >
            {t("common.save")}
          </Button>
        </div>
      </div>
    </FormModal>
  );
}

function Detail({ label, value, ltr = false }: { label: string; value: React.ReactNode; ltr?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2 first:pt-1 last:pb-1">
      <dt className="shrink-0 text-muted">{label}</dt>
      <dd className={`min-w-0 truncate font-medium text-text ${ltr ? "ltr-field" : ""}`}>{value}</dd>
    </div>
  );
}

function BalanceDialog({
  open,
  onClose,
  userId,
  balance,
  invalidate,
}: {
  open: boolean;
  onClose: () => void;
  userId: number;
  balance: number;
  invalidate: (string | number)[][];
}) {
  const { t } = useTranslation();
  const [amount, setAmount] = useState("");
  const [notify, setNotify] = useState(true);
  const adjust = usePanelAction(panelUsersApi.adjustBalance, { invalidate });

  function submit(sign: 1 | -1) {
    const value = Number(amount.replace(/,/g, ""));
    if (!Number.isFinite(value) || value <= 0) return;
    adjust.mutate(
      { user_id: userId, delta: sign * Math.round(value), notify },
      {
        onSuccess: () => {
          setAmount("");
          onClose();
        },
      }
    );
  }

  return (
    <FormModal open={open} onClose={onClose} title={t("panel.userDetail.balanceTitle", { id: userId })}>
      <div className="space-y-4">
        <p className="text-sm text-muted">{t("panel.userDetail.currentBalance")}: {formatToman(balance)}</p>
        <Input
          label={t("panel.userDetail.amountToman")}
          inputMode="numeric"
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
          placeholder={t("panel.userDetail.egFiftyThousand")}
        />
        <Toggle checked={notify} onChange={setNotify} label={t("panel.userDetail.notifyUser")} />
        <div className="flex justify-end gap-2">
          <Button size="sm" variant="danger" loading={adjust.isPending} onClick={() => submit(-1)}>
            {t("panel.userDetail.deduct")}
          </Button>
          <Button size="sm" loading={adjust.isPending} onClick={() => submit(1)}>
            {t("panel.userDetail.add")}
          </Button>
        </div>
      </div>
    </FormModal>
  );
}

function MessageDialog({ open, onClose, userId }: { open: boolean; onClose: () => void; userId: number }) {
  const { t } = useTranslation();
  const [text, setText] = useState("");
  const send = usePanelAction(panelUsersApi.sendMessage);

  return (
    <FormModal open={open} onClose={onClose} title={t("panel.userDetail.messageTitle", { id: userId })}>
      <div className="space-y-4">
        <label className="block text-sm">
          <span className="mb-1.5 block text-muted">{t("panel.broadcast.messageText")}</span>
          <textarea
            rows={5}
            value={text}
            onChange={(event) => setText(event.target.value)}
            maxLength={4000}
            className="w-full rounded-md border border-border bg-surface p-3 text-text outline-none focus:border-primary focus:ring-4 focus:ring-primary/10"
          />
        </label>
        <div className="flex justify-end gap-2">
          <Button size="sm" variant="ghost" onClick={onClose}>
            {t("panel.common.dismiss")}
          </Button>
          <Button
            size="sm"
            loading={send.isPending}
            disabled={!text.trim()}
            onClick={() =>
              send.mutate(
                { user_id: userId, text: text.trim() },
                {
                  onSuccess: () => {
                    setText("");
                    onClose();
                  },
                }
              )
            }
          >
            {t("panel.userDetail.send")}
          </Button>
        </div>
      </div>
    </FormModal>
  );
}
