import { useState } from "react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge, Button, ErrorState, Input, Pagination } from "../../components/ui";
import { formatNumber, formatUnixDate } from "../../lib/format";
import { panelServicesApi } from "../../api/panel";
import type { PanelServiceRow } from "../../types/panel";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { ConfirmButton, DataTable, SectionCard, SelectField, Toolbar } from "./components";
import type { Column } from "./components";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

const stateOptions = (t: TFunction) => [
  { value: "", label: t("panel.common.all") },
  { value: "active", label: t("panel.common.active") },
  { value: "expired", label: t("panel.common.expired") },
  { value: "test", label: t("panel.services.trial") },
];

export default function AdminServicesPage() {
  const { t } = useTranslation();
  const [filters, setFilters] = useState({ q: "", panel: "", state: "" });
  const [draft, setDraft] = useState({ q: "", panel: "", state: "" });
  const [page, setPage] = useState(1);

  const query = usePanelQuery(["services", filters.q, filters.panel, filters.state, page], (auth) =>
    panelServicesApi.listServices({ ...auth, ...filters, page, limit: 25 })
  );

  const toggle = usePanelAction(panelServicesApi.toggleService, { invalidate: [["services"]] });
  const remove = usePanelAction(panelServicesApi.deleteService, { invalidate: [["services"]] });

  const panelOptions = [
    { value: "", label: t("panel.common.allPanels") },
    ...(query.data?.panels || []).map((panel) => ({ value: String(panel.code), label: panel.name })),
  ];

  const columns: Column<PanelServiceRow>[] = [
    { key: "code", header: t("panel.common.code"), cell: (row) => <code className="ltr-field text-xs">{row.code}</code> },
    {
      key: "username",
      header: t("panel.services.username"),
      cell: (row) => <span className="ltr-field text-xs">{row.username || "—"}</span>,
    },
    {
      key: "user",
      header: t("common.user"),
      secondary: true,
      cell: (row) => <code className="ltr-field text-xs text-muted">{row.user_id ?? "—"}</code>,
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
        if (row.expired) return <Badge tone="danger">{t("panel.common.expired")}</Badge>;
        if (!row.enable) return <Badge tone="warning">{t("panel.common.inactive")}</Badge>;
        if (row.is_test) return <Badge tone="primary">{t("panel.services.trial")}</Badge>;
        return <Badge tone="success">{t("panel.common.active")}</Badge>;
      },
    },
    {
      key: "actions",
      header: t("panel.common.actions"),
      cell: (row) => (
        <div className="flex flex-wrap gap-1.5">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => toggle.mutate({ code: row.code, enabled: !row.enable })}
          >
            {row.enable ? t("panel.common.inactive") : t("panel.common.active")}
          </Button>
          <ConfirmButton
            size="sm"
            variant="danger"
            message={t("panel.services.deleteWarning")}
            onConfirm={() => remove.mutate({ code: row.code })}
          >
            {t("common.delete")}
          </ConfirmButton>
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title={t("panel.common.services")}
        subtitle={query.data ? t("panel.services.countLabel", { count: formatNumber(query.data.meta.total) }) : undefined}
      />

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
            placeholder={t("panel.services.searchPlaceholder")}
          />
        </div>
        <div className="w-40">
          <SelectField
            label={t("panel.common.panel")}
            options={panelOptions}
            value={draft.panel}
            onChange={(event) => setDraft((prev) => ({ ...prev, panel: event.target.value }))}
          />
        </div>
        <div className="w-36">
          <SelectField
            label={t("panel.common.status")}
            options={stateOptions(t)}
            value={draft.state}
            onChange={(event) => setDraft((prev) => ({ ...prev, state: event.target.value }))}
          />
        </div>
        <Button size="md" type="submit" variant="secondary">
          {t("panel.common.applyFilter")}
        </Button>
      </Toolbar>

      {query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : (
        <SectionCard title={t("panel.services.title")}>
          <DataTable
            columns={columns}
            rows={query.data?.services || []}
            rowKey={(row) => row.code}
            loading={query.isLoading}
            emptyTitle={t("panel.services.empty")}
          />
          <div className="mt-4">
            <Pagination page={page} totalPages={query.data?.meta.total_pages || 1} onChange={setPage} />
          </div>
        </SectionCard>
      )}
    </>
  );
}
