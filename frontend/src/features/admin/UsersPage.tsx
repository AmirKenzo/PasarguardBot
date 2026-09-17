import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowDownAZ, ArrowUpAZ, Ban, ChevronLeft, Search, SlidersHorizontal, User, X } from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge, ErrorState, IconBadge, Input, Pagination, Skeleton } from "../../components/ui";
import { formatNumber, formatToman, formatUnixDate } from "../../lib/format";
import { panelUsersApi } from "../../api/panel";
import type { UserState } from "../../types/panel";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { ConfirmButton, IconMenuButton, MenuHeader, MenuRow, SectionCard } from "./components";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

const STATE_TONE: Record<UserState, "success" | "warning" | "danger" | "muted"> = {
  active: "success",
  banned: "danger",
  blocked_bot: "warning",
  deleted: "muted",
};

const TAB_ACTIVE_CLASSES: Record<"success" | "warning" | "danger" | "muted", string> = {
  success: "bg-success/12 text-success",
  warning: "bg-warning/12 text-warning",
  danger: "bg-danger/12 text-danger",
  muted: "bg-surface-2 text-text",
};

const stateLabels = (t: TFunction): Record<UserState, string> => ({
  active: t("panel.common.active"),
  banned: t("panel.users.stateBanned"),
  blocked_bot: t("panel.users.stateBlockedBot"),
  deleted: t("panel.users.stateDeleted"),
});

/** Quick top-level tabs — the one filter dimension used often enough to skip the dropdown. */
const stateTabs = (t: TFunction) => [
  { value: "", label: t("panel.common.all"), tone: "muted" as const },
  { value: "active", label: t("panel.common.active"), tone: "success" as const },
  { value: "banned", label: t("panel.users.stateBanned"), tone: "danger" as const },
  { value: "blocked_bot", label: t("panel.users.stateBlockedBot"), tone: "warning" as const },
  { value: "deleted", label: t("panel.users.stateDeleted"), tone: "muted" as const },
];

const sortOptions = (t: TFunction) => [
  { value: "newest", label: t("panel.users.sortNewest"), icon: ArrowDownAZ },
  { value: "oldest", label: t("panel.users.sortOldest"), icon: ArrowUpAZ },
];

const EMPTY_FILTERS = { q: "", state: "", sort: "newest" };
const EMPTY_SEARCH = { q: "" };
const SEARCH_DEBOUNCE_MS = 400;

export default function AdminUsersPage() {
  const { t } = useTranslation();

  // Free text is debounced so typing doesn't fire a request per keystroke;
  // discrete filters (tabs, dropdown rows) apply straight to `filters`.
  const [searchInputs, setSearchInputs] = useState(EMPTY_SEARCH);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [page, setPage] = useState(1);

  useEffect(() => {
    const handle = setTimeout(() => {
      setFilters((prev) => ({ ...prev, ...searchInputs }));
      setPage(1);
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(handle);
  }, [searchInputs]);

  const query = usePanelQuery(["users", filters.q, filters.state, filters.sort, page], (auth) =>
    panelUsersApi.listUsers({ ...auth, ...filters, page, limit: 10 })
  );

  const block = usePanelAction(panelUsersApi.setBlocked, { invalidate: [["users"]] });

  const rows = query.data?.users || [];

  function updateFilter(key: "state" | "sort", value: string) {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  }
  function clearFilters() {
    setSearchInputs(EMPTY_SEARCH);
    setFilters(EMPTY_FILTERS);
    setPage(1);
  }

  const hasAdvancedFilters = filters.sort !== "newest";
  const hasActiveFilters = searchInputs.q !== "" || filters.state !== "" || hasAdvancedFilters;

  return (
    <>
      <PageHeader
        title={t("panel.common.users")}
        subtitle={query.data ? t("panel.users.countLabel", { count: formatNumber(query.data.meta.total) }) : undefined}
      />

      <SectionCard title={t("panel.users.title")} description={t("panel.users.hint")}>
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-surface p-2.5">
          <div className="relative min-w-0 flex-1 sm:max-w-[12rem] sm:flex-none sm:w-48">
            <Search size={13} className="pointer-events-none absolute top-1/2 -translate-y-1/2 text-muted ltr:left-2.5 rtl:right-2.5" />
            <Input
              dense
              ltr
              placeholder={t("panel.users.searchPlaceholder")}
              aria-label={t("panel.common.search")}
              className="ltr:pl-7 rtl:pr-7"
              value={searchInputs.q}
              onChange={(e) => setSearchInputs((s) => ({ ...s, q: e.target.value }))}
            />
          </div>

          <IconMenuButton
            icon={SlidersHorizontal}
            title={t("panel.transactions.advancedFilters")}
            active={hasAdvancedFilters}
            badge={hasAdvancedFilters}
            width={192}
            heightEstimate={180}
          >
            {(close) => (
              <>
                <MenuHeader title={t("panel.users.sortLabel")} />
                {sortOptions(t).map((opt) => (
                  <MenuRow
                    key={opt.value}
                    icon={opt.icon}
                    label={opt.label}
                    active={opt.value === filters.sort}
                    onClick={() => {
                      updateFilter("sort", opt.value);
                      close();
                    }}
                  />
                ))}
              </>
            )}
          </IconMenuButton>

          {hasActiveFilters && (
            <button
              type="button"
              onClick={clearFilters}
              title={t("panel.transactions.clearFilters")}
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted transition-colors hover:bg-danger/10 hover:text-danger"
            >
              <X size={14} />
            </button>
          )}

          <div className="flex flex-wrap items-center gap-1 sm:ms-auto">
            {stateTabs(t).map((tab) => {
              const active = tab.value === filters.state;
              return (
                <button
                  key={tab.value}
                  type="button"
                  onClick={() => updateFilter("state", tab.value)}
                  className={`shrink-0 rounded-md px-2 py-1.5 text-xs font-medium transition-colors ${
                    active ? TAB_ACTIVE_CLASSES[tab.tone] : "text-muted hover:bg-surface-2 hover:text-text"
                  }`}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>

        {query.isError ? (
          <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
        ) : query.isLoading ? (
          <div className="mt-4 space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-14 w-full rounded-md" />
            ))}
          </div>
        ) : rows.length ? (
          <div className="mt-2 divide-y divide-border/60">
            {rows.map((row) => {
              // Only an admin ban is reversible from here — BlockedBot/deleted
              // self-clear once the user interacts with the bot again, an
              // admin "unblock" click cannot fix either.
              const canToggleBlock = row.state === "active" || row.state === "banned";
              return (
                <div key={row.id} className="flex flex-wrap items-center gap-2.5 py-2.5 first:pt-0 last:pb-0">
                  <IconBadge icon={User} tone="muted" size="sm" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5 text-xs font-semibold text-text">
                      <Link to={`/panel/users/${row.id}`} className="ltr-field text-primary hover:underline">
                        #{row.id}
                      </Link>
                      {row.number && <span className="ltr-field font-normal text-muted">{row.number}</span>}
                    </div>
                    <div className="text-[11px] text-muted">
                      {t("panel.users.service")} <span className="ltr-field">{formatNumber(row.services)}</span>
                      {row.joined_at ? ` · ${formatUnixDate(row.joined_at)}` : ""}
                    </div>
                  </div>
                  <div className="text-[11px] font-semibold text-text">{formatToman(row.balance)}</div>
                  <span
                    title={
                      row.state === "blocked_bot"
                        ? t("panel.users.blockedBotHint")
                        : row.state === "deleted"
                          ? t("panel.users.deletedHint")
                          : undefined
                    }
                  >
                    <Badge tone={STATE_TONE[row.state]}>{stateLabels(t)[row.state]}</Badge>
                  </span>
                  <div className="flex shrink-0 items-center gap-1">
                    <Link to={`/panel/users/${row.id}`} title={t("panel.users.manage")}>
                      <span className="flex h-7 w-7 items-center justify-center rounded-md border border-border text-muted transition-colors hover:border-primary/40 hover:bg-primary/10 hover:text-primary">
                        <ChevronLeft size={13} />
                      </span>
                    </Link>
                    {canToggleBlock && (
                      <ConfirmButton
                        size="sm"
                        variant="ghost"
                        className={`!h-7 !w-7 !px-0 ${row.state === "banned" ? "text-success hover:bg-success/10" : "text-danger hover:bg-danger/10"}`}
                        title={row.state === "banned" ? t("panel.common.unblock") : t("panel.users.blocked")}
                        message={
                          row.state === "banned"
                            ? t("panel.users.unblockConfirm", { id: row.id })
                            : t("panel.users.blockConfirm", { id: row.id })
                        }
                        onConfirm={() => block.mutate({ user_id: row.id, blocked: row.state !== "banned", notify: true })}
                      >
                        <Ban size={13} />
                      </ConfirmButton>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="py-8 text-center text-sm text-muted">{t("panel.users.empty")}</p>
        )}

        <div className="mt-4">
          <Pagination page={page} totalPages={query.data?.meta.total_pages || 1} onChange={setPage} />
        </div>
      </SectionCard>
    </>
  );
}
