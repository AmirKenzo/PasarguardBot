import { useState } from "react";
import { Link } from "react-router-dom";
import { ChevronLeft } from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge, Button, ErrorState, Input, Pagination } from "../../components/ui";
import { formatNumber, formatToman, formatUnixDate } from "../../lib/format";
import { panelUsersApi } from "../../api/panel";
import type { PanelUserRow } from "../../types/panel";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { ConfirmButton, DataTable, SectionCard, SelectField, Toolbar } from "./components";
import type { Column } from "./components";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

const stateOptions = (t: TFunction) => [
  { value: "", label: t("panel.common.all") },
  { value: "active", label: t("panel.common.active") },
  { value: "blocked", label: t("panel.users.blocked") },
];

export default function AdminUsersPage() {
  const { t } = useTranslation();
  const [filters, setFilters] = useState({ q: "", state: "" });
  const [draft, setDraft] = useState({ q: "", state: "" });
  const [page, setPage] = useState(1);

  const query = usePanelQuery(["users", filters.q, filters.state, page], (auth) =>
    panelUsersApi.listUsers({ ...auth, ...filters, page, limit: 25 })
  );

  const block = usePanelAction(panelUsersApi.setBlocked, { invalidate: [["users"]] });

  const columns: Column<PanelUserRow>[] = [
    {
      key: "id",
      header: t("panel.common.id"),
      cell: (row) => (
        <Link to={`/panel/users/${row.id}`} className="ltr-field text-xs font-medium text-primary hover:underline">
          {row.id}
        </Link>
      ),
    },
    {
      key: "number",
      header: t("panel.users.phone"),
      secondary: true,
      cell: (row) => <span className="ltr-field text-xs text-muted">{row.number || "—"}</span>,
    },
    { key: "balance", header: t("panel.users.balance"), cell: (row) => formatToman(row.balance) },
    { key: "services", header: t("panel.users.service"), secondary: true, cell: (row) => formatNumber(row.services) },
    {
      key: "joined",
      header: t("panel.users.joined"),
      secondary: true,
      cell: (row) => <span className="text-xs text-muted">{row.joined_at ? formatUnixDate(row.joined_at) : "—"}</span>,
    },
    {
      key: "status",
      header: t("panel.common.status"),
      cell: (row) => (row.blocked ? <Badge tone="danger">{t("panel.users.blocked")}</Badge> : <Badge tone="success">{t("panel.common.active")}</Badge>),
    },
    {
      key: "actions",
      header: t("panel.common.actions"),
      cell: (row) => (
        <div className="flex flex-wrap items-center gap-1.5">
          <Link to={`/panel/users/${row.id}`}>
            <Button size="sm" variant="secondary">
              {t("panel.users.manage")}
              <ChevronLeft size={14} />
            </Button>
          </Link>
          <ConfirmButton
            size="sm"
            variant={row.blocked ? "ghost" : "danger"}
            message={
              row.blocked
                ? t("panel.users.unblockConfirm", { id: row.id })
                : t("panel.users.blockConfirm", { id: row.id })
            }
            onConfirm={() => block.mutate({ user_id: row.id, blocked: !row.blocked, notify: true })}
          >
            {row.blocked ? t("panel.common.unblock") : t("panel.users.blocked")}
          </ConfirmButton>
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader title={t("panel.common.users")} subtitle={query.data ? t("panel.users.countLabel", { count: formatNumber(query.data.meta.total) }) : undefined} />

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
            placeholder={t("panel.users.searchPlaceholder")}
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
        <SectionCard title={t("panel.users.title")} description={t("panel.users.hint")}>
          <DataTable
            columns={columns}
            rows={query.data?.users || []}
            rowKey={(row) => row.id}
            loading={query.isLoading}
            emptyTitle={t("panel.users.empty")}
          />
          <div className="mt-4">
            <Pagination page={page} totalPages={query.data?.meta.total_pages || 1} onChange={setPage} />
          </div>
        </SectionCard>
      )}
    </>
  );
}
