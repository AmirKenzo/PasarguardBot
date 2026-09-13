import { useState } from "react";
import { Plus } from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button, ErrorState, Input, Skeleton } from "../../components/ui";
import { formatToman } from "../../lib/format";
import { panelPlansApi } from "../../api/panel";
import type { PanelPlanRow, PanelPlanSaveRequest } from "../../types/panel";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { ConfirmButton, DataTable, FormModal, SectionCard, SelectField } from "./components";
import type { Column } from "./components";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

const planTypeLabels = (t: TFunction): Record<string, string> => ({
  volume: t("panel.plans.volumeBased"),
  fair_usage: t("panel.plans.fairUse"),
});

const resetLabels = (t: TFunction): Record<string, string> => ({
  no_reset: t("resetStrategy.no_reset"),
  day: t("resetStrategy.day"),
  week: t("resetStrategy.week"),
  month: t("resetStrategy.month"),
  year: t("resetStrategy.year"),
});

const styleLabels = (t: TFunction): Record<string, string> => ({
  "": t("panel.common.default"),
  primary: t("panel.common.blue"),
  success: t("panel.common.green"),
  danger: t("panel.common.red"),
});

type Draft = Omit<PanelPlanSaveRequest, "session_token" | "init_data">;

const EMPTY_DRAFT: Draft = {
  plan_id: null,
  panel_code: 0,
  storage: 0,
  duration: 30,
  price: 0,
  plan_type: "volume",
  data_limit_reset_strategy: "no_reset",
  ip_limit: 0,
  display_button_text: "",
  button_style: "",
  button_icon: "",
};

export default function AdminPlansPage() {
  const { t } = useTranslation();
  const [panelFilter, setPanelFilter] = useState("");
  const [draft, setDraft] = useState<Draft | null>(null);

  const query = usePanelQuery(["plans", panelFilter], (auth) =>
    panelPlansApi.listPlans({ ...auth, panel: panelFilter })
  );
  const save = usePanelAction(panelPlansApi.savePlan, { invalidate: [["plans"]] });
  const remove = usePanelAction(panelPlansApi.deletePlan, { invalidate: [["plans"]] });

  const panels = query.data?.panels || [];
  const panelOptions = panels.map((panel) => ({ value: String(panel.code), label: panel.name }));

  const columns: Column<PanelPlanRow>[] = [
    { key: "id", header: "#", cell: (row) => <code className="ltr-field text-xs">{row.id}</code> },
    { key: "panel", header: t("panel.common.panel"), cell: (row) => row.panel || `#${row.panel_code}` },
    { key: "storage", header: t("panel.common.volume"), cell: (row) => (row.storage ? `${row.storage} GB` : t("common.unlimited")) },
    { key: "duration", header: t("panel.common.period"), cell: (row) => t("panel.plans.durationDays", { count: row.duration }) },
    { key: "price", header: t("panel.plans.price"), cell: (row) => formatToman(row.price) },
    {
      key: "type",
      header: t("panel.common.type"),
      secondary: true,
      cell: (row) => planTypeLabels(t)[row.plan_type] || row.plan_type,
    },
    { key: "ip", header: "IP", secondary: true, cell: (row) => row.ip_limit || t("panel.plans.noLimit") },
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
                plan_id: row.id,
                panel_code: row.panel_code,
                storage: row.storage,
                duration: row.duration,
                price: row.price,
                plan_type: row.plan_type,
                data_limit_reset_strategy: row.data_limit_reset_strategy,
                ip_limit: row.ip_limit,
                display_button_text: row.display_button_text || "",
                button_style: row.button_style || "",
                button_icon: row.button_icon ? String(row.button_icon) : "",
              })
            }
          >
            {t("common.edit")}
          </Button>
          <ConfirmButton
            size="sm"
            variant="danger"
            message={t("panel.plans.deleteConfirm")}
            onConfirm={() => remove.mutate({ plan_id: row.id })}
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
        title={t("panel.common.salesPlans")}
        subtitle={t("panel.plans.subtitle")}
        action={
          <Button
            size="sm"
            disabled={!panels.length}
            onClick={() => setDraft({ ...EMPTY_DRAFT, panel_code: panels[0]?.code || 0 })}
          >
            <Plus size={16} />
            {t("panel.common.addPlan")}
          </Button>
        }
      />

      {query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : (
        <SectionCard
          title={t("panel.common.plans")}
          actions={
            <div className="w-44">
              <SelectField
                options={[{ value: "", label: t("panel.common.allPanels") }, ...panelOptions]}
                value={panelFilter}
                onChange={(event) => setPanelFilter(event.target.value)}
              />
            </div>
          }
        >
          {query.isLoading ? (
            <Skeleton className="h-40 w-full" />
          ) : (
            <DataTable
              columns={columns}
              rows={query.data?.plans || []}
              rowKey={(row) => row.id}
              emptyTitle={t("panel.common.noPlansDefined")}
              emptyDescription={panels.length ? undefined : t("panel.common.addPanelFirst")}
            />
          )}
        </SectionCard>
      )}

      <FormModal
        open={draft !== null}
        onClose={() => setDraft(null)}
        title={draft?.plan_id ? t("panel.plans.editTitle", { id: draft.plan_id }) : t("panel.common.addPlan")}
      >
        {draft && (
          <div className="grid gap-3 sm:grid-cols-2">
            <SelectField
              label={t("panel.common.panel")}
              options={panelOptions}
              value={String(draft.panel_code)}
              onChange={(event) => setDraft({ ...draft, panel_code: Number(event.target.value) })}
            />
            <Input
              label={t("panel.plans.volumeGb")}
              inputMode="decimal"
              value={String(draft.storage ?? 0)}
              onChange={(event) => setDraft({ ...draft, storage: Number(event.target.value) || 0 })}
            />
            <Input
              label={t("panel.common.periodDays")}
              inputMode="numeric"
              value={String(draft.duration)}
              onChange={(event) => setDraft({ ...draft, duration: Number(event.target.value) || 0 })}
            />
            <Input
              label={t("panel.plans.priceToman")}
              inputMode="numeric"
              value={String(draft.price)}
              onChange={(event) => setDraft({ ...draft, price: Number(event.target.value) || 0 })}
            />
            <SelectField
              label={t("panel.plans.planType")}
              options={(query.data?.plan_types || []).map((value) => ({
                value,
                label: planTypeLabels(t)[value] || value,
              }))}
              value={draft.plan_type}
              onChange={(event) => setDraft({ ...draft, plan_type: event.target.value })}
            />
            <SelectField
              label={t("panel.plans.volumeReset")}
              options={(query.data?.reset_strategies || []).map((value) => ({
                value,
                label: resetLabels(t)[value] || value,
              }))}
              value={draft.data_limit_reset_strategy}
              onChange={(event) => setDraft({ ...draft, data_limit_reset_strategy: event.target.value })}
            />
            <Input
              label={t("panel.plans.ipLimit")}
              inputMode="numeric"
              value={String(draft.ip_limit ?? 0)}
              onChange={(event) => setDraft({ ...draft, ip_limit: Number(event.target.value) || 0 })}
            />
            <Input
              label={t("panel.plans.buttonText")}
              value={draft.display_button_text || ""}
              onChange={(event) => setDraft({ ...draft, display_button_text: event.target.value })}
            />
            <SelectField
              label={t("panel.common.buttonColour")}
              options={(query.data?.button_styles || []).map((value) => ({
                value,
                label: styleLabels(t)[value] || value,
              }))}
              value={draft.button_style || ""}
              onChange={(event) => setDraft({ ...draft, button_style: event.target.value })}
            />
            <Input
              label={t("panel.common.premiumEmojiId")}
              ltr
              inputMode="numeric"
              value={draft.button_icon || ""}
              onChange={(event) => setDraft({ ...draft, button_icon: event.target.value })}
            />
            <div className="col-span-full flex justify-end gap-2">
              <Button size="sm" variant="ghost" onClick={() => setDraft(null)}>
                {t("panel.common.dismiss")}
              </Button>
              <Button
                size="sm"
                loading={save.isPending}
                disabled={!draft.panel_code || !draft.duration}
                onClick={() => save.mutate(draft, { onSuccess: () => setDraft(null) })}
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
