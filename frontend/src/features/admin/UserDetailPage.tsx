import { useState } from "react";
import { useParams } from "react-router-dom";
import { MessageSquare, Wallet } from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge, Button, ErrorState, Input, Skeleton } from "../../components/ui";
import { formatNumber, formatToman, formatUnixDate } from "../../lib/format";
import { panelUsersApi } from "../../api/panel";
import type { PanelUserServiceRow, PanelUserTransactionRow } from "../../types/panel";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { ConfirmButton, DataTable, FormModal, SectionCard, StatTile, Toggle } from "./components";
import type { Column } from "./components";
import { useTranslation } from "react-i18next";

const TX_TONE: Record<string, "success" | "warning" | "danger" | "muted"> = {
  approved: "success",
  pending: "warning",
  rejected: "danger",
};

export default function AdminUserDetailPage() {
  const { t } = useTranslation();
  const params = useParams();
  const userId = Number(params.userId);

  const [balanceOpen, setBalanceOpen] = useState(false);
  const [messageOpen, setMessageOpen] = useState(false);

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

  const serviceColumns: Column<PanelUserServiceRow>[] = [
    { key: "code", header: t("panel.common.code"), cell: (row) => <code className="ltr-field text-xs">{row.code}</code> },
    {
      key: "username",
      header: t("panel.services.username"),
      cell: (row) => <span className="ltr-field text-xs">{row.username || "—"}</span>,
    },
    { key: "panel", header: t("panel.common.panel"), secondary: true, cell: (row) => row.panel || "—" },
    {
      key: "size",
      header: t("panel.common.volume"),
      secondary: true,
      cell: (row) => (row.package_size ? `${row.package_size} GB` : t("common.unlimited")),
    },
    {
      key: "expires",
      header: t("panel.common.expiry"),
      secondary: true,
      cell: (row) => (
        <span className="text-xs text-muted">{row.expiration_time ? formatUnixDate(row.expiration_time) : "—"}</span>
      ),
    },
    {
      key: "status",
      header: t("panel.common.status"),
      cell: (row) => {
        if (!row.enable) return <Badge tone="warning">{t("panel.common.inactive")}</Badge>;
        if (row.is_test) return <Badge tone="primary">{t("panel.services.trial")}</Badge>;
        return <Badge tone="success">{t("panel.common.active")}</Badge>;
      },
    },
  ];

  const txColumns: Column<PanelUserTransactionRow>[] = [
    { key: "id", header: "#", cell: (row) => <code className="ltr-field text-xs">{row.id}</code> },
    { key: "amount", header: t("panel.common.amount"), cell: (row) => formatToman(row.amount) },
    {
      key: "status",
      header: t("panel.common.status"),
      cell: (row) => <Badge tone={TX_TONE[row.status || ""] || "muted"}>{row.status || "—"}</Badge>,
    },
    {
      key: "created",
      header: t("panel.common.time"),
      secondary: true,
      cell: (row) => (
        <span className="text-xs text-muted">{row.created_at ? formatUnixDate(row.created_at) : "—"}</span>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title={t("panel.userDetail.title", { id: user.id })}
        subtitle={user.number || t("panel.userDetail.noPhone")}
        back="/panel/users"
        action={
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="secondary" onClick={() => setBalanceOpen(true)}>
              <Wallet size={15} />
              {t("panel.users.balance")}
            </Button>
            <Button size="sm" variant="secondary" onClick={() => setMessageOpen(true)}>
              <MessageSquare size={15} />
              {t("panel.userDetail.message")}
            </Button>
            <ConfirmButton
              size="sm"
              variant={user.blocked ? "secondary" : "danger"}
              message={
                user.blocked
                  ? t("panel.userDetail.unblockConfirm", { id: user.id })
                  : t("panel.userDetail.blockConfirm", { id: user.id })
              }
              onConfirm={() => block.mutate({ user_id: user.id, blocked: !user.blocked, notify: true })}
            >
              {user.blocked ? t("panel.common.unblock") : t("panel.userDetail.block")}
            </ConfirmButton>
          </div>
        }
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label={t("panel.userDetail.walletBalance")} value={formatToman(user.balance)} tone="primary" />
        <StatTile label={t("panel.common.services")} value={formatNumber(user.services)} />
        <StatTile label={t("panel.userDetail.successfulInvites")} value={formatNumber(referrals)} />
        <StatTile
          label={t("panel.common.status")}
          value={user.blocked ? t("panel.users.blocked") : t("panel.common.active")}
          hint={user.status || undefined}
          tone={user.blocked ? "danger" : "success"}
        />
      </div>

      <SectionCard title={t("panel.userDetail.profile")}>
        <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">
          <Detail label={t("panel.userDetail.numericId")} value={user.id} ltr />
          <Detail label={t("panel.userDetail.phoneNumber")} value={user.number || t("panel.userDetail.notSet")} ltr={Boolean(user.number)} />
          <Detail label={t("panel.userDetail.accountStatus")} value={user.status || "—"} />
          <Detail label={t("panel.userDetail.joinedAt")} value={user.joined_at ? formatUnixDate(user.joined_at) : "—"} />
        </dl>
      </SectionCard>

      <SectionCard title={t("panel.userDetail.servicesTitle", { count: formatNumber(services.length) })}>
        <DataTable
          columns={serviceColumns}
          rows={services}
          rowKey={(row) => row.code}
          emptyTitle={t("panel.userDetail.noServices")}
        />
      </SectionCard>

      <SectionCard title={t("panel.userDetail.recentTransactions")}>
        <DataTable
          columns={txColumns}
          rows={transactions}
          rowKey={(row) => row.id}
          emptyTitle={t("panel.userDetail.noTransactions")}
        />
      </SectionCard>

      <BalanceDialog
        open={balanceOpen}
        onClose={() => setBalanceOpen(false)}
        userId={user.id}
        balance={user.balance}
        invalidate={invalidate}
      />
      <MessageDialog open={messageOpen} onClose={() => setMessageOpen(false)} userId={user.id} />
    </>
  );
}

function Detail({ label, value, ltr = false }: { label: string; value: React.ReactNode; ltr?: boolean }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className={`mt-0.5 text-sm text-text ${ltr ? "ltr-field" : ""}`}>{value}</dd>
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
