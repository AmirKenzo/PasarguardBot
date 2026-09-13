import { useState } from "react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge, Button, ErrorState, Input, Pagination } from "../../components/ui";
import { formatNumber, formatToman, formatUnixDate } from "../../lib/format";
import { panelResellersApi } from "../../api/panel";
import type { PanelResellerRow } from "../../types/panel";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { ConfirmButton, DataTable, FormModal, SectionCard, SelectField, Toolbar } from "./components";
import type { Column } from "./components";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

const GB = 1024 ** 3;

const statusLabels = (t: TFunction): Record<string, string> => ({
  active: t("panel.common.active"),
  suspended: t("panel.resellers.suspended"),
  expired: t("panel.common.expired"),
});

const STATUS_TONE: Record<string, "success" | "warning" | "danger" | "muted"> = {
  active: "success",
  suspended: "warning",
  expired: "danger",
};

const pricingLabels = (t: TFunction): Record<string, string> => ({
  fixed: t("panel.common.flatRate"),
  per_gb: t("panel.common.perGigabyte"),
  per_tb: t("panel.common.perTerabyte"),
  hourly: t("panel.common.hourly"),
  usage: t("panel.common.metered"),
});

interface EditDraft {
  code: number;
  status: string;
  usage_cap_gb: string;
  max_users: string;
  extend_days: string;
}

export default function AdminResellersPage() {
  const { t } = useTranslation();
  const [filters, setFilters] = useState({ q: "", status: "" });
  const [draftFilters, setDraftFilters] = useState({ q: "", status: "" });
  const [page, setPage] = useState(1);
  const [edit, setEdit] = useState<EditDraft | null>(null);
  const [detailCode, setDetailCode] = useState<number | null>(null);

  const query = usePanelQuery(["resellers", filters.q, filters.status, page], (auth) =>
    panelResellersApi.listResellers({ ...auth, ...filters, page, limit: 25 })
  );

  const detail = usePanelQuery(
    ["reseller", detailCode],
    (auth) => panelResellersApi.getReseller({ ...auth, code: detailCode as number }),
    { enabled: detailCode !== null }
  );

  const invalidate = [["resellers"], ["reseller"]];
  const update = usePanelAction(panelResellersApi.updateReseller, { invalidate });
  const remove = usePanelAction(panelResellersApi.deleteReseller, { invalidate });

  const statusOptions = [
    { value: "", label: t("panel.common.all") },
    ...(query.data?.statuses || []).map((value) => ({ value, label: statusLabels(t)[value] || value })),
  ];

  const columns: Column<PanelResellerRow>[] = [
    { key: "code", header: t("panel.common.code"), cell: (row) => <code className="ltr-field text-xs">{row.code}</code> },
    {
      key: "telegram",
      header: t("panel.resellers.telegram"),
      cell: (row) => <code className="ltr-field text-xs">{row.telegram_id ?? "—"}</code>,
    },
    {
      key: "username",
      header: t("panel.resellers.panelUser"),
      secondary: true,
      cell: (row) => <span className="ltr-field text-xs">{row.username || "—"}</span>,
    },
    { key: "panel", header: t("panel.common.panel"), secondary: true, cell: (row) => row.panel || "—" },
    {
      key: "pricing",
      header: t("panel.common.pricingModel"),
      secondary: true,
      cell: (row) => pricingLabels(t)[row.pricing_mode] || row.pricing_mode,
    },
    {
      key: "cap",
      header: t("panel.resellers.usageCap"),
      secondary: true,
      cell: (row) => (row.usage_cap_bytes ? `${(row.usage_cap_bytes / GB).toFixed(1)} GB` : t("panel.resellers.noCap")),
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
      cell: (row) => <Badge tone={STATUS_TONE[row.status] || "muted"}>{statusLabels(t)[row.status] || row.status}</Badge>,
    },
    {
      key: "actions",
      header: t("panel.common.actions"),
      cell: (row) => (
        <div className="flex flex-wrap gap-1.5">
          <Button size="sm" variant="ghost" onClick={() => setDetailCode(row.code)}>
            {t("panel.common.details")}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() =>
              setEdit({
                code: row.code,
                status: row.status,
                usage_cap_gb: row.usage_cap_bytes ? String(Math.round((row.usage_cap_bytes / GB) * 100) / 100) : "",
                max_users: String(row.max_users || 0),
                extend_days: "",
              })
            }
          >
            {t("common.edit")}
          </Button>
          <ConfirmButton
            size="sm"
            variant="danger"
            message={t("panel.resellers.deleteConfirm")}
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
        title={t("panel.common.resellers")}
        subtitle={query.data ? t("panel.resellers.countLabel", { count: formatNumber(query.data.meta.total) }) : undefined}
      />

      <Toolbar
        onSubmit={() => {
          setPage(1);
          setFilters(draftFilters);
        }}
      >
        <div className="min-w-[12rem] flex-1">
          <Input
            label={t("panel.common.search")}
            value={draftFilters.q}
            onChange={(event) => setDraftFilters((prev) => ({ ...prev, q: event.target.value }))}
            placeholder={t("panel.resellers.searchPlaceholder")}
          />
        </div>
        <div className="w-36">
          <SelectField
            label={t("panel.common.status")}
            options={statusOptions}
            value={draftFilters.status}
            onChange={(event) => setDraftFilters((prev) => ({ ...prev, status: event.target.value }))}
          />
        </div>
        <Button size="md" type="submit" variant="secondary">
          {t("panel.common.applyFilter")}
        </Button>
      </Toolbar>

      {query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : (
        <SectionCard title={t("panel.resellers.title")}>
          <DataTable
            columns={columns}
            rows={query.data?.resellers || []}
            rowKey={(row) => row.code}
            loading={query.isLoading}
            emptyTitle={t("panel.resellers.empty")}
          />
          <div className="mt-4">
            <Pagination page={page} totalPages={query.data?.meta.total_pages || 1} onChange={setPage} />
          </div>
        </SectionCard>
      )}

      <FormModal
        open={detailCode !== null}
        onClose={() => setDetailCode(null)}
        title={t("panel.resellers.detailTitle", { name: detail.data?.reseller?.username || detailCode || "" })}
      >
        {detail.isLoading ? (
          <p className="py-6 text-center text-sm text-muted">{t("panel.resellers.loading")}</p>
        ) : detail.data?.reseller ? (
          <div className="space-y-4">
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <Detail label={t("panel.resellers.telegramUser")} value={detail.data.reseller.telegram_id ?? "—"} ltr />
              <Detail label={t("panel.common.panel")} value={detail.data.reseller.panel || "—"} />
              <Detail
                label={t("panel.resellers.purchasedVolume")}
                value={`${detail.data.reseller.purchased_volume || 0} GB`}
              />
              <Detail label={t("panel.common.maxUsers")} value={formatNumber(detail.data.reseller.max_users || 0)} />
              <Detail
                label={t("panel.resellers.createdAt")}
                value={detail.data.reseller.createtime ? formatUnixDate(detail.data.reseller.createtime) : "—"}
              />
              <Detail
                label={t("panel.common.expiry")}
                value={
                  detail.data.reseller.expiration_time ? formatUnixDate(detail.data.reseller.expiration_time) : "—"
                }
              />
            </dl>
            <div>
              <p className="mb-2 text-xs font-medium text-muted">{t("panel.resellers.invoiceHistory")}</p>
              {detail.data.snapshots.length ? (
                <ul className="space-y-1.5 text-sm">
                  {detail.data.snapshots.map((snapshot) => (
                    <li key={snapshot.id} className="flex items-center justify-between rounded-md bg-surface-2 px-3 py-2">
                      <span className="text-xs text-muted">
                        {snapshot.snapshot_at ? formatUnixDate(snapshot.snapshot_at) : "—"}
                      </span>
                      <span>{(snapshot.used_traffic / GB).toFixed(2)} GB</span>
                      <span className="font-medium">{formatToman(snapshot.billed_amount)}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted">{t("panel.resellers.invoicesEmpty")}</p>
              )}
            </div>
          </div>
        ) : (
          <p className="py-6 text-center text-sm text-muted">{detail.error?.message || t("panel.resellers.notFound")}</p>
        )}
      </FormModal>

      <FormModal open={edit !== null} onClose={() => setEdit(null)} title={t("panel.resellers.editTitle", { code: edit?.code ?? "" })}>
        {edit && (
          <div className="space-y-3">
            <SelectField
              label={t("panel.common.status")}
              options={(query.data?.statuses || []).map((value) => ({
                value,
                label: statusLabels(t)[value] || value,
              }))}
              value={edit.status}
              onChange={(event) => setEdit({ ...edit, status: event.target.value })}
            />
            <Input
              label={t("panel.resellers.usageCapGb")}
              inputMode="decimal"
              placeholder={t("panel.resellers.emptyMeansNoCap")}
              value={edit.usage_cap_gb}
              onChange={(event) => setEdit({ ...edit, usage_cap_gb: event.target.value })}
            />
            <Input
              label={t("panel.common.maxUsers")}
              inputMode="numeric"
              value={edit.max_users}
              onChange={(event) => setEdit({ ...edit, max_users: event.target.value })}
            />
            <Input
              label={t("panel.resellers.extendExpiry")}
              inputMode="numeric"
              placeholder={t("panel.common.egThirty")}
              value={edit.extend_days}
              onChange={(event) => setEdit({ ...edit, extend_days: event.target.value })}
            />
            <div className="flex justify-end gap-2">
              <Button size="sm" variant="ghost" onClick={() => setEdit(null)}>
                {t("panel.common.dismiss")}
              </Button>
              <Button
                size="sm"
                loading={update.isPending}
                onClick={() =>
                  update.mutate(
                    {
                      code: edit.code,
                      status: edit.status,
                      usage_cap_gb: edit.usage_cap_gb.trim() ? Number(edit.usage_cap_gb) : null,
                      max_users: Number(edit.max_users) || 0,
                      extend_days: Number(edit.extend_days) || 0,
                    },
                    { onSuccess: () => setEdit(null) }
                  )
                }
              >
                {t("common.save")}
              </Button>
            </div>
          </div>
        )}
      </FormModal>
    </>
  );
}

function Detail({ label, value, ltr = false }: { label: string; value: React.ReactNode; ltr?: boolean }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className={`mt-0.5 text-text ${ltr ? "ltr-field" : ""}`}>{value}</dd>
    </div>
  );
}
