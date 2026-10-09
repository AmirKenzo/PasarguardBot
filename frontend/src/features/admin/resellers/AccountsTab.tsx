import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Button, ErrorState, Input, Pagination } from "../../../components/ui";
import { panelResellersApi } from "../../../api/panel";
import { formatNumber, formatUnixDate } from "../../../lib/format";
import type { PanelResellerRow } from "../../../types/panel";
import { usePanelQuery } from "../../../queries/usePanelApi";
import { DataTable, SectionCard, SelectField, Toolbar } from "../components";
import type { Column } from "../components";
import AccountDetailModal from "./AccountDetailModal";
import { StatusBadge } from "./parts";
import { pricingLabels, statusLabels } from "./labels";

type Navigate = (tab: string, extra?: Record<string, string>) => void;

interface Filters {
  q: string;
  status: string;
  mode: string;
  panel: string;
}

export default function AccountsTab({ onNavigate }: { onNavigate: Navigate }) {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const initial: Filters = {
    q: searchParams.get("q") || "",
    status: searchParams.get("status") || "",
    mode: searchParams.get("mode") || "",
    panel: searchParams.get("panel") || "",
  };
  const [filters, setFilters] = useState<Filters>(initial);
  const [draft, setDraft] = useState<Filters>(initial);
  const [page, setPage] = useState(1);
  const openParam = Number(searchParams.get("open")) || null;
  const [openCode, setOpenCode] = useState<number | null>(openParam);

  const query = usePanelQuery(["resellers", filters, page], (auth) =>
    panelResellersApi.listResellers({
      ...auth,
      q: filters.q,
      status: filters.status,
      pricing_mode: filters.mode,
      panel_code: filters.panel ? Number(filters.panel) : null,
      page,
      limit: 25,
    })
  );

  const closeDetail = () => {
    setOpenCode(null);
    if (searchParams.has("open")) {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.delete("open");
        return next;
      });
    }
  };

  const statuses = query.data?.statuses || [];
  const modes = query.data?.pricing_modes || [];
  const panels = query.data?.panels || [];

  const columns: Column<PanelResellerRow>[] = [
    {
      key: "account",
      header: t("panel.resellerHub.accounts.account"),
      cell: (row) => (
        <div className="min-w-0">
          <p className="ltr-field truncate text-sm font-medium text-text">{row.username || "—"}</p>
          <p className="ltr-field text-[11px] text-muted">#{row.code}</p>
        </div>
      ),
    },
    {
      key: "telegram",
      header: t("panel.resellers.telegram"),
      cell: (row) => <code className="ltr-field text-xs">{row.telegram_id ?? "—"}</code>,
    },
    { key: "panel", header: t("panel.common.panel"), secondary: true, cell: (row) => row.panel || "—" },
    {
      key: "mode",
      header: t("panel.resellerHub.planType"),
      secondary: true,
      cell: (row) => pricingLabels(t)[row.pricing_mode] || row.pricing_mode,
    },
    {
      key: "expires",
      header: t("panel.common.expiry"),
      secondary: true,
      cell: (row) => (
        <span className="text-xs text-muted">
          {row.expiration_time ? formatUnixDate(row.expiration_time) : t("panel.resellerHub.unlimited")}
        </span>
      ),
    },
    { key: "status", header: t("panel.common.status"), cell: (row) => <StatusBadge status={row.status} /> },
    {
      key: "actions",
      header: "",
      cell: (row) => (
        <Button size="sm" variant="secondary" onClick={() => setOpenCode(row.code)}>
          {t("panel.resellerHub.accounts.manage")}
        </Button>
      ),
    },
  ];

  return (
    <>
      <Toolbar
        onSubmit={() => {
          setPage(1);
          setFilters(draft);
        }}
      >
        <div className="min-w-[12rem] flex-1">
          <Input
            label={t("panel.common.search")}
            value={draft.q}
            onChange={(event) => setDraft((prev) => ({ ...prev, q: event.target.value }))}
            placeholder={t("panel.resellers.searchPlaceholder")}
          />
        </div>
        <div className="w-36">
          <SelectField
            label={t("panel.common.status")}
            options={[
              { value: "", label: t("panel.common.all") },
              ...statuses.map((value) => ({ value, label: statusLabels(t)[value] || value })),
            ]}
            value={draft.status}
            onChange={(event) => setDraft((prev) => ({ ...prev, status: event.target.value }))}
          />
        </div>
        <div className="w-36">
          <SelectField
            label={t("panel.resellerHub.planType")}
            options={[
              { value: "", label: t("panel.common.all") },
              ...modes.map((value) => ({ value, label: pricingLabels(t)[value] || value })),
            ]}
            value={draft.mode}
            onChange={(event) => setDraft((prev) => ({ ...prev, mode: event.target.value }))}
          />
        </div>
        {panels.length > 1 && (
          <div className="w-36">
            <SelectField
              label={t("panel.common.panel")}
              options={[
                { value: "", label: t("panel.common.allPanels") },
                ...panels.map((panel) => ({ value: String(panel.code), label: panel.name })),
              ]}
              value={draft.panel}
              onChange={(event) => setDraft((prev) => ({ ...prev, panel: event.target.value }))}
            />
          </div>
        )}
        <Button size="md" type="submit" variant="secondary">
          {t("panel.common.applyFilter")}
        </Button>
      </Toolbar>

      {query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : (
        <SectionCard
          title={t("panel.resellers.title")}
          description={
            query.data ? t("panel.resellers.countLabel", { count: formatNumber(query.data.meta.total) }) : undefined
          }
        >
          <DataTable
            columns={columns}
            rows={query.data?.resellers || []}
            rowKey={(row) => row.code}
            loading={query.isLoading}
            emptyTitle={t("panel.resellerHub.accountsEmpty")}
          />
          <div className="mt-4">
            <Pagination page={page} totalPages={query.data?.meta.total_pages || 1} onChange={setPage} />
          </div>
        </SectionCard>
      )}

      <AccountDetailModal code={openCode} onClose={closeDetail} onNavigate={onNavigate} />
    </>
  );
}
