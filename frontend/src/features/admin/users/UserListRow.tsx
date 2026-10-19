import { Link } from "react-router-dom";
import { Ban, ChevronLeft, Clock, Sparkles, User } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";
import { Badge } from "../../../components/ui";
import { formatNumber, formatRelativeTime, formatToman, formatUnixDate } from "../../../lib/format";
import type { PanelUserRow, UserState } from "../../../types/panel";
import { ConfirmButton } from "../components";

const STATE_TONE: Record<UserState, "success" | "warning" | "danger" | "muted"> = {
  active: "success",
  banned: "danger",
  blocked_bot: "warning",
  deleted: "muted",
};

const stateLabels = (t: TFunction): Record<UserState, string> => ({
  active: t("panel.common.active"),
  banned: t("panel.users.stateBanned"),
  blocked_bot: t("panel.users.stateBlockedBot"),
  deleted: t("panel.users.stateDeleted"),
});

function stateHint(t: TFunction, state: UserState): string | undefined {
  if (state === "blocked_bot") return t("panel.users.blockedBotHint");
  if (state === "deleted") return t("panel.users.deletedHint");
  return undefined;
}

function UserAvatar({ isNew }: { isNew: boolean }) {
  return (
    <span
      className={`relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full ring-1 ring-inset ${
        isNew ? "bg-primary/15 text-primary ring-primary/25" : "bg-surface-2 text-muted ring-border"
      }`}
    >
      <User size={16} />
      {isNew && (
        <span className="absolute -bottom-0.5 -end-0.5 flex h-3 w-3" aria-hidden>
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-60" />
          <span className="relative inline-flex h-3 w-3 rounded-full bg-success ring-2 ring-surface" />
        </span>
      )}
    </span>
  );
}

export interface UserListRowProps {
  row: PanelUserRow;
  onToggleBlock: (row: PanelUserRow) => void;
}

export function UserListRow({ row, onToggleBlock }: UserListRowProps) {
  const { t } = useTranslation();
  const isNew = Boolean(row.is_new);
  // Only an admin ban is reversible from here — BlockedBot/deleted
  // self-clear once the user interacts with the bot again, an
  // admin "unblock" click cannot fix either.
  const canToggleBlock = row.state === "active" || row.state === "banned";
  const banned = row.state === "banned";

  return (
    <div
      className={`relative flex items-center gap-2.5 rounded-lg px-2.5 py-2.5 transition-colors ${
        isNew ? "bg-primary/[0.06] ring-1 ring-inset ring-primary/15" : "hover:bg-surface-2/70"
      }`}
    >
      {isNew && <span className="absolute inset-y-2.5 start-0 w-[3px] rounded-full bg-primary" aria-hidden />}
      <UserAvatar isNew={isNew} />

      <div className="min-w-0 flex-1">
        <div className="flex min-w-0 items-center gap-1.5 text-xs">
          <Link to={`/panel/users/${row.id}`} className="ltr-field font-bold text-primary hover:underline">
            #{row.id}
          </Link>
          {row.number && <span className="ltr-field hidden truncate text-muted sm:inline">{row.number}</span>}
          {isNew && (
            <span className="inline-flex shrink-0 items-center gap-0.5 rounded-full bg-primary/15 px-1.5 py-0.5 text-3xs font-bold text-primary">
              <Sparkles size={10} />
              {t("panel.users.newBadge")}
            </span>
          )}
        </div>
        <div className="mt-0.5 flex min-w-0 items-center gap-x-1 overflow-hidden whitespace-nowrap text-2xs text-muted">
          {row.joined_at ? (
            isNew ? (
              <span className="inline-flex shrink-0 items-center gap-1 text-primary">
                <Clock size={11} />
                {formatRelativeTime(row.joined_at)}
              </span>
            ) : (
              <span className="min-w-0 truncate">{formatUnixDate(row.joined_at)}</span>
            )
          ) : null}
          <span className="shrink-0">
            {row.joined_at ? "· " : ""}
            {t("panel.users.service")} <span className="ltr-field">{formatNumber(row.services)}</span>
          </span>
          {row.number && (
            <span className="min-w-0 truncate sm:hidden">
              · <span className="ltr-field">{row.number}</span>
            </span>
          )}
        </div>
      </div>

      <div className="hidden shrink-0 text-2xs font-semibold text-text sm:block">{formatToman(row.balance)}</div>
      <span className="shrink-0" title={stateHint(t, row.state)}>
        <Badge tone={STATE_TONE[row.state]}>{stateLabels(t)[row.state]}</Badge>
      </span>
      <div className="flex shrink-0 items-center gap-1">
        <Link to={`/panel/users/${row.id}`} title={t("panel.users.manage")}>
          <span className="flex h-7 w-7 items-center justify-center rounded-full border border-border text-muted transition-colors hover:border-primary/40 hover:bg-primary/10 hover:text-primary">
            <ChevronLeft size={13} className="ltr:rotate-180" />
          </span>
        </Link>
        {canToggleBlock && (
          <ConfirmButton
            size="sm"
            variant="ghost"
            className={`!h-7 !w-7 !rounded-full !px-0 ${banned ? "text-success hover:bg-success/10" : "text-danger hover:bg-danger/10"}`}
            title={banned ? t("panel.common.unblock") : t("panel.users.blocked")}
            message={banned ? t("panel.users.unblockConfirm", { id: row.id }) : t("panel.users.blockConfirm", { id: row.id })}
            onConfirm={() => onToggleBlock(row)}
          >
            <Ban size={13} />
          </ConfirmButton>
        )}
      </div>
    </div>
  );
}
