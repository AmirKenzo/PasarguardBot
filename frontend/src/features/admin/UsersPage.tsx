import { useEffect, useState } from "react";
import { keepPreviousData } from "@tanstack/react-query";
import { ArrowDownAZ, ArrowUpAZ, Search, SlidersHorizontal, Sparkles, X } from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { ErrorState, Input, Pagination, Skeleton } from "../../components/ui";
import { formatNumber } from "../../lib/format";
import { panelUsersApi } from "../../api/panel";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { IconMenuButton, MenuHeader, MenuRow, SectionCard } from "./components";
import { UserListRow } from "./users/UserListRow";
import { UsersStatCards } from "./users/UsersStatCards";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

const TAB_ACTIVE_CLASSES: Record<"primary" | "success" | "warning" | "danger" | "muted", string> = {
  primary: "bg-primary/12 text-primary",
  success: "bg-success/12 text-success",
  warning: "bg-warning/12 text-warning",
  danger: "bg-danger/12 text-danger",
  muted: "bg-surface-2 text-text",
};

/** Quick top-level tabs — the one filter dimension used often enough to skip the dropdown. */
const stateTabs = (t: TFunction) => [
  { value: "", label: t("panel.common.all"), tone: "muted" as const },
  { value: "new", label: t("panel.users.stateNew"), tone: "primary" as const },
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
    panelUsersApi.listUsers({ ...auth, ...filters, page, limit: 10 }),
    { placeholderData: keepPreviousData }
  );

  // Prefix ["users"] also covers ["users", "stats"], so the cards refresh after a block.
  const stats = usePanelQuery(["users", "stats"], (auth) => panelUsersApi.usersStats(auth));
  const block = usePanelAction(panelUsersApi.setBlocked, { invalidate: [["users"]] });

  const rows = query.data?.users || [];
  const newCount = query.data?.new_count ?? 0;

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
        subtitle={query.data ? t("panel.users.countLabel", { count: query.data.meta.total }) : undefined}
      />

      <div className="mb-3">
        <UsersStatCards stats={stats.data} />
      </div>

      <SectionCard title={t("panel.users.title")} description={t("panel.users.hint")}>
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-surface p-2.5">
          <div className="relative min-w-0 flex-1 sm:max-w-[12rem] sm:flex-none sm:w-48">
            <Search size={13} className="pointer-events-none absolute top-1/2 -translate-y-1/2 text-muted start-2.5" />
            <Input
              dense
              ltr
              placeholder={t("panel.users.searchPlaceholder")}
              aria-label={t("panel.common.search")}
              className="ps-7"
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

          <div className="no-scrollbar -mx-0.5 flex w-full items-center gap-1 overflow-x-auto px-0.5 sm:mx-0 sm:ms-auto sm:w-auto sm:flex-wrap sm:overflow-visible sm:px-0">
            {stateTabs(t).map((tab) => {
              const active = tab.value === filters.state;
              return (
                <button
                  key={tab.value}
                  type="button"
                  onClick={() => updateFilter("state", tab.value)}
                  className={`inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-md px-2 py-1.5 text-xs font-medium transition-colors ${
                    active ? TAB_ACTIVE_CLASSES[tab.tone] : "text-muted hover:bg-surface-2 hover:text-text"
                  }`}
                >
                  {tab.value === "new" && <Sparkles size={12} />}
                  {tab.label}
                  {tab.value === "new" && newCount > 0 && (
                    <span className="inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-primary px-1 text-3xs font-bold text-primary-text">
                      {formatNumber(newCount)}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {query.isError ? (
          <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
        ) : query.isLoading ? (
          <div className="mt-2 space-y-1.5">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-14 w-full rounded-lg" />
            ))}
          </div>
        ) : rows.length ? (
          <div
            className={`mt-2 space-y-1.5 transition-opacity ${query.isPlaceholderData ? "opacity-60" : ""}`}
            aria-busy={query.isPlaceholderData || undefined}
          >
            {rows.map((row) => (
              <UserListRow
                key={row.id}
                row={row}
                onToggleBlock={(target) =>
                  block.mutate({ user_id: target.id, blocked: target.state !== "banned", notify: true })
                }
              />
            ))}
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
