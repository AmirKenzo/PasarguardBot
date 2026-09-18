import { useEffect, useState } from "react";
import { Filter, Power, Search, Server, SlidersHorizontal, Trash2, X } from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge, ErrorState, IconBadge, Input, Pagination, Skeleton } from "../../components/ui";
import { formatBytes, formatExpiry, formatNumber } from "../../lib/format";
import { panelServicesApi } from "../../api/panel";
import type { PanelServiceRow } from "../../types/panel";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { ConfirmButton, IconMenuButton, MenuHeader, MenuRow, SectionCard } from "./components";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

const STATE_TONE: Record<string, "success" | "warning" | "danger" | "primary" | "muted"> = {
  active: "success",
  inactive: "warning",
  expired: "danger",
  test: "primary",
};

const TAB_ACTIVE_CLASSES: Record<"success" | "warning" | "danger" | "primary" | "muted", string> = {
  primary: "bg-primary/12 text-primary",
  success: "bg-success/12 text-success",
  warning: "bg-warning/12 text-warning",
  danger: "bg-danger/12 text-danger",
  muted: "bg-surface-2 text-text",
};

/** Quick top-level tabs — the one filter dimension used often enough to skip the dropdown. */
const stateTabs = (t: TFunction) => [
  { value: "", label: t("panel.common.all"), tone: "muted" as const },
  { value: "active", label: t("panel.common.active"), tone: "success" as const },
  { value: "expired", label: t("panel.common.expired"), tone: "danger" as const },
  { value: "test", label: t("panel.services.trial"), tone: "primary" as const },
];

function serviceState(row: PanelServiceRow): "active" | "inactive" | "expired" | "test" {
  if (row.expired) return "expired";
  if (!row.enable) return "inactive";
  if (row.is_test) return "test";
  return "active";
}

const EMPTY_FILTERS = { q: "", panel: "", state: "" };
const EMPTY_SEARCH = { q: "" };
const SEARCH_DEBOUNCE_MS = 400;

export default function AdminServicesPage() {
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

  const query = usePanelQuery(["services", filters.q, filters.panel, filters.state, page], (auth) =>
    panelServicesApi.listServices({ ...auth, ...filters, page, limit: 10 })
  );

  const toggle = usePanelAction(panelServicesApi.toggleService, { invalidate: [["services"]] });
  const remove = usePanelAction(panelServicesApi.deleteService, { invalidate: [["services"]] });

  const rows = query.data?.services || [];
  const panelOptions = [
    { value: "", label: t("panel.common.allPanels"), icon: Filter },
    ...(query.data?.panels || []).map((panel) => ({ value: String(panel.code), label: panel.name, icon: Server })),
  ];

  function updateFilter(key: "panel" | "state", value: string) {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  }
  function clearFilters() {
    setSearchInputs(EMPTY_SEARCH);
    setFilters(EMPTY_FILTERS);
    setPage(1);
  }

  const hasAdvancedFilters = filters.panel !== "";
  const hasActiveFilters = searchInputs.q !== "" || filters.state !== "" || hasAdvancedFilters;

  return (
    <>
      <PageHeader
        title={t("panel.common.services")}
        subtitle={query.data ? t("panel.services.countLabel", { count: formatNumber(query.data.meta.total) }) : undefined}
      />

      <SectionCard title={t("panel.services.title")}>
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-surface p-2.5">
          <div className="relative min-w-0 flex-1 sm:max-w-[12rem] sm:flex-none sm:w-48">
            <Search size={13} className="pointer-events-none absolute top-1/2 -translate-y-1/2 text-muted ltr:left-2.5 rtl:right-2.5" />
            <Input
              dense
              placeholder={t("panel.services.searchPlaceholder")}
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
            heightEstimate={220}
          >
            {(close) => (
              <>
                <MenuHeader title={t("panel.common.panel")} />
                {panelOptions.map((opt) => (
                  <MenuRow
                    key={opt.value}
                    icon={opt.icon}
                    label={opt.label}
                    active={opt.value === filters.panel}
                    onClick={() => {
                      updateFilter("panel", opt.value);
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
              const state = serviceState(row);
              const expiry = formatExpiry(row.expiration_time);
              return (
                <div key={row.code} className="flex flex-wrap items-center gap-2.5 py-2.5 first:pt-0 last:pb-0">
                  <IconBadge icon={Server} tone="muted" size="sm" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5 text-xs font-semibold text-text">
                      {row.username || "—"}
                      <code className="ltr-field text-[11px] font-normal text-muted">#{row.code}</code>
                    </div>
                    <div className="text-[11px] text-muted">
                      {t("common.user")} <span className="ltr-field">{row.user_id ?? "—"}</span>
                      {row.panel ? ` · ${row.panel}` : ""}
                    </div>
                  </div>
                  <div className="text-[11px] text-muted">
                    {row.package_size ? formatBytes(row.package_size, 1) : t("common.unlimited")}
                  </div>
                  <div className="text-[11px] text-muted">{expiry.remaining}</div>
                  <Badge tone={STATE_TONE[state]}>
                    {state === "test" ? t("panel.services.trial") : t(`panel.common.${state}`)}
                  </Badge>
                  <div className="flex shrink-0 items-center gap-1">
                    <ConfirmButton
                      size="sm"
                      variant="ghost"
                      className="!h-7 !w-7 !px-0"
                      title={row.enable ? t("panel.common.inactive") : t("panel.common.active")}
                      message={t(row.enable ? "panel.services.disableConfirm" : "panel.services.enableConfirm", { id: row.code })}
                      onConfirm={() => toggle.mutate({ code: row.code, enabled: !row.enable })}
                    >
                      <Power size={13} className={row.enable ? "text-warning" : "text-success"} />
                    </ConfirmButton>
                    <ConfirmButton
                      size="sm"
                      variant="ghost"
                      className="!h-7 !w-7 !px-0 text-danger hover:bg-danger/10"
                      title={t("common.delete")}
                      message={t("panel.services.deleteWarning")}
                      onConfirm={() => remove.mutate({ code: row.code })}
                    >
                      <Trash2 size={13} />
                    </ConfirmButton>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="py-8 text-center text-sm text-muted">{t("panel.services.empty")}</p>
        )}

        <div className="mt-4">
          <Pagination page={page} totalPages={query.data?.meta.total_pages || 1} onChange={setPage} />
        </div>
      </SectionCard>
    </>
  );
}
