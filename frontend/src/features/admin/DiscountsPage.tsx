import { useState } from "react";
import { Plus } from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge, Button, ErrorState, Input, Pagination } from "../../components/ui";
import { formatNumber, formatUnixDate } from "../../lib/format";
import { panelDiscountsApi } from "../../api/panel";
import { DISCOUNT_CODE_PATTERN } from "../../types/panel";
import type { PanelDiscountRow } from "../../types/panel";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { ConfirmButton, DataTable, FormModal, SectionCard, Toggle } from "./components";
import type { Column } from "./components";
import { useTranslation } from "react-i18next";

interface Draft {
  code_id: number | null;
  code: string;
  discount_percentage: string;
  usage_limit: string;
  expires_days: string;
  user_id: string;
  is_public: boolean;
}

const EMPTY_DRAFT: Draft = {
  code_id: null,
  code: "",
  discount_percentage: "10",
  usage_limit: "1",
  expires_days: "",
  user_id: "",
  is_public: true,
};

export default function AdminDiscountsPage() {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const [draft, setDraft] = useState<Draft | null>(null);

  const query = usePanelQuery(["discounts", page], (auth) =>
    panelDiscountsApi.listDiscounts({ ...auth, page, limit: 25 })
  );
  const save = usePanelAction(panelDiscountsApi.saveDiscount, { invalidate: [["discounts"]] });
  const remove = usePanelAction(panelDiscountsApi.deleteDiscount, { invalidate: [["discounts"]] });

  const codeIsValid = draft ? DISCOUNT_CODE_PATTERN.test(draft.code.trim()) : false;

  const columns: Column<PanelDiscountRow>[] = [
    { key: "code", header: t("panel.common.code"), cell: (row) => <code className="ltr-field text-xs">{row.code}</code> },
    { key: "percent", header: t("panel.discounts.percent"), cell: (row) => t("panel.discounts.percentValue", { value: row.discount_percentage }) },
    {
      key: "usage",
      header: t("panel.discounts.used"),
      cell: (row) => `${formatNumber(row.times_used)} / ${formatNumber(row.usage_limit)}`,
    },
    {
      key: "expires",
      header: t("panel.common.expiry"),
      secondary: true,
      cell: (row) => (
        <span className="text-xs text-muted">
          {row.expiration_date ? formatUnixDate(row.expiration_date) : t("panel.discounts.noExpiry")}
        </span>
      ),
    },
    {
      key: "user",
      header: t("common.user"),
      secondary: true,
      cell: (row) =>
        row.user_id ? <code className="ltr-field text-xs">{row.user_id}</code> : <Badge tone="primary">{t("panel.discounts.public")}</Badge>,
    },
    {
      key: "status",
      header: t("panel.common.status"),
      cell: (row) => {
        if (row.expired) return <Badge tone="danger">{t("panel.common.expired")}</Badge>;
        if (row.exhausted) return <Badge tone="muted">{t("panel.discounts.usedUp")}</Badge>;
        return <Badge tone="success">{t("panel.common.active")}</Badge>;
      },
    },
    {
      key: "actions",
      header: t("panel.common.actions"),
      cell: (row) => (
        <div className="flex gap-1.5">
          <Button
            size="sm"
            variant="ghost"
            onClick={() =>
              setDraft({
                code_id: row.id,
                code: row.code,
                discount_percentage: String(row.discount_percentage),
                usage_limit: String(row.usage_limit),
                expires_days: row.expiration_date
                  ? String(Math.max(0, Math.ceil((row.expiration_date - Date.now() / 1000) / 86400)))
                  : "",
                user_id: row.user_id ? String(row.user_id) : "",
                is_public: row.is_public,
              })
            }
          >
            {t("common.edit")}
          </Button>
          <ConfirmButton
            size="sm"
            variant="danger"
            message={t("panel.discounts.deleteCodeConfirm", { code: row.code })}
            onConfirm={() => remove.mutate({ code_id: row.id })}
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
        title={t("panel.discounts.heading")}
        subtitle={query.data ? t("panel.discounts.countLabel", { count: formatNumber(query.data.meta.total) }) : undefined}
        action={
          <Button size="sm" onClick={() => setDraft({ ...EMPTY_DRAFT })}>
            <Plus size={16} />
            {t("panel.discounts.create")}
          </Button>
        }
      />

      {query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : (
        <SectionCard title={t("panel.discounts.title")}>
          <DataTable
            columns={columns}
            rows={query.data?.discounts || []}
            rowKey={(row) => row.id}
            loading={query.isLoading}
            emptyTitle={t("panel.discounts.empty")}
          />
          <div className="mt-4">
            <Pagination page={page} totalPages={query.data?.meta.total_pages || 1} onChange={setPage} />
          </div>
        </SectionCard>
      )}

      <FormModal
        open={draft !== null}
        onClose={() => setDraft(null)}
        title={draft?.code_id ? t("panel.discounts.editTitle", { code: draft.code }) : t("panel.common.createDiscount")}
      >
        {draft && (
          <div className="space-y-3">
            <Input
              label={t("panel.common.discountCode")}
              ltr
              value={draft.code}
              onChange={(event) => setDraft({ ...draft, code: event.target.value })}
              error={draft.code && !codeIsValid ? t("panel.discounts.codeRules") : null}
            />
            <Input
              label={t("panel.discounts.discountPercent")}
              inputMode="numeric"
              value={draft.discount_percentage}
              onChange={(event) => setDraft({ ...draft, discount_percentage: event.target.value })}
            />
            <Input
              label={t("panel.discounts.usageCap")}
              inputMode="numeric"
              value={draft.usage_limit}
              onChange={(event) => setDraft({ ...draft, usage_limit: event.target.value })}
            />
            <Input
              label={t("panel.discounts.validityDays")}
              inputMode="numeric"
              placeholder={t("panel.discounts.emptyMeansNoExpiry")}
              value={draft.expires_days}
              onChange={(event) => setDraft({ ...draft, expires_days: event.target.value })}
            />
            <Input
              label={t("panel.discounts.assignToUser")}
              ltr
              inputMode="numeric"
              placeholder={t("panel.discounts.telegramId")}
              value={draft.user_id}
              onChange={(event) => setDraft({ ...draft, user_id: event.target.value })}
            />
            <Toggle
              checked={draft.is_public}
              onChange={(is_public) => setDraft({ ...draft, is_public })}
              label={t("panel.discounts.isPublic")}
            />
            <div className="flex justify-end gap-2">
              <Button size="sm" variant="ghost" onClick={() => setDraft(null)}>
                {t("panel.common.dismiss")}
              </Button>
              <Button
                size="sm"
                loading={save.isPending}
                disabled={!codeIsValid}
                onClick={() =>
                  save.mutate(
                    {
                      code_id: draft.code_id,
                      code: draft.code.trim(),
                      discount_percentage: Number(draft.discount_percentage) || 0,
                      usage_limit: Number(draft.usage_limit) || 1,
                      expires_days: draft.expires_days.trim() ? Number(draft.expires_days) : null,
                      user_id: draft.user_id.trim() ? Number(draft.user_id) : null,
                      is_public: draft.is_public,
                    },
                    { onSuccess: () => setDraft(null) }
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
