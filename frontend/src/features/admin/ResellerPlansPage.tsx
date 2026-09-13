import { useState } from "react";
import { Plus } from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge, Button, ErrorState, Input, Skeleton } from "../../components/ui";
import { formatToman } from "../../lib/format";
import { panelResellersApi } from "../../api/panel";
import type { PanelResellerPlanRow, PanelResellerPlanSaveRequest } from "../../types/panel";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { ConfirmButton, DataTable, FormModal, SectionCard, SelectField, Toggle } from "./components";
import type { Column } from "./components";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

const pricingLabels = (t: TFunction): Record<string, string> => ({
  fixed: t("panel.common.flatRate"),
  per_gb: t("panel.common.perGigabyte"),
  per_tb: t("panel.common.perTerabyte"),
  hourly: t("panel.common.hourly"),
  usage: t("panel.common.metered"),
});

const styleLabels = (t: TFunction): Record<string, string> => ({
  "": t("panel.common.default"),
  primary: t("panel.common.blue"),
  success: t("panel.common.green"),
  danger: t("panel.common.red"),
});

type Draft = Omit<PanelResellerPlanSaveRequest, "session_token" | "init_data">;

const EMPTY_DRAFT: Draft = {
  plan_id: null,
  panel_code: 0,
  pricing_mode: "fixed",
  price: 0,
  unit_price: 0,
  min_volume: 0,
  max_volume: 0,
  volume_step: 1,
  max_users: 0,
  duration: 0,
  role_id: 0,
  role_name: "",
  enable: true,
  display_button_text: "",
  button_style: "",
  button_icon: "",
};

export default function AdminResellerPlansPage() {
  const { t } = useTranslation();
  const [draft, setDraft] = useState<Draft | null>(null);

  const query = usePanelQuery(["reseller-plans"], (auth) => panelResellersApi.listResellerPlans(auth));
  const save = usePanelAction(panelResellersApi.saveResellerPlan, { invalidate: [["reseller-plans"]] });
  const remove = usePanelAction(panelResellersApi.deleteResellerPlan, { invalidate: [["reseller-plans"]] });

  const panels = query.data?.panels || [];
  const panelOptions = panels.map((panel) => ({ value: String(panel.code), label: panel.name }));

  const columns: Column<PanelResellerPlanRow>[] = [
    { key: "id", header: "#", cell: (row) => <code className="ltr-field text-xs">{row.id}</code> },
    { key: "panel", header: t("panel.common.panel"), cell: (row) => row.panel || `#${row.panel_code}` },
    { key: "mode", header: t("panel.resellerPlans.model"), cell: (row) => pricingLabels(t)[row.pricing_mode] || row.pricing_mode },
    { key: "price", header: t("panel.resellerPlans.basePrice"), cell: (row) => formatToman(row.price) },
    { key: "unit", header: t("panel.resellerPlans.unitPrice"), secondary: true, cell: (row) => formatToman(row.unit_price) },
    { key: "duration", header: t("panel.common.period"), secondary: true, cell: (row) => (row.duration ? t("panel.plans.durationDays", { count: row.duration }) : "—") },
    {
      key: "status",
      header: t("panel.common.status"),
      cell: (row) => (row.enable ? <Badge tone="success">{t("panel.common.active")}</Badge> : <Badge tone="muted">{t("panel.common.inactive")}</Badge>),
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
                plan_id: row.id,
                panel_code: row.panel_code,
                pricing_mode: row.pricing_mode,
                price: row.price,
                unit_price: row.unit_price,
                min_volume: row.min_volume,
                max_volume: row.max_volume,
                volume_step: row.volume_step,
                max_users: row.max_users,
                duration: row.duration,
                role_id: row.role_id,
                role_name: row.role_name || "",
                enable: row.enable,
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
            message={t("panel.resellerPlans.deleteConfirm")}
            onConfirm={() => remove.mutate({ plan_id: row.id })}
          >
            {t("common.delete")}
          </ConfirmButton>
        </div>
      ),
    },
  ];

  function numberField(label: string, key: keyof Draft, hint?: string) {
    if (!draft) return null;
    return (
      <Input
        label={label}
        inputMode="decimal"
        value={String(draft[key] ?? 0)}
        onChange={(event) => setDraft({ ...draft, [key]: Number(event.target.value) || 0 })}
        {...(hint ? { placeholder: hint } : {})}
      />
    );
  }

  return (
    <>
      <PageHeader
        title={t("panel.common.resellerPlans")}
        subtitle={t("panel.resellerPlans.subtitle")}
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
        <SectionCard title={t("panel.common.plans")}>
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
        title={draft?.plan_id ? t("panel.resellerPlans.editTitle", { id: draft.plan_id }) : t("panel.common.addResellerPlan")}
      >
        {draft && (
          <div className="grid gap-3 sm:grid-cols-2">
            <SelectField
              label={t("panel.common.panel")}
              options={panelOptions}
              value={String(draft.panel_code)}
              onChange={(event) => setDraft({ ...draft, panel_code: Number(event.target.value) })}
            />
            <SelectField
              label={t("panel.common.pricingModel")}
              options={(query.data?.pricing_modes || []).map((value) => ({
                value,
                label: pricingLabels(t)[value] || value,
              }))}
              value={draft.pricing_mode || "fixed"}
              onChange={(event) => setDraft({ ...draft, pricing_mode: event.target.value })}
            />
            {numberField(t("panel.resellerPlans.basePrice"), "price")}
            {numberField(t("panel.resellerPlans.unitPrice"), "unit_price")}
            {numberField(t("panel.resellerPlans.minVolume"), "min_volume")}
            {numberField(t("panel.resellerPlans.maxVolume"), "max_volume")}
            {numberField(t("panel.resellerPlans.volumeStep"), "volume_step")}
            {numberField(t("panel.common.maxUsers"), "max_users")}
            {numberField(t("panel.common.periodDays"), "duration")}
            {numberField(t("panel.resellerPlans.roleId"), "role_id")}
            <Input
              label={t("panel.resellerPlans.roleName")}
              value={draft.role_name || ""}
              onChange={(event) => setDraft({ ...draft, role_name: event.target.value })}
            />
            <Input
              label={t("panel.common.buttonText")}
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
            <div className="col-span-full">
              <Toggle
                checked={draft.enable ?? true}
                onChange={(enable) => setDraft({ ...draft, enable })}
                label={t("panel.resellerPlans.enabled")}
              />
            </div>
            <div className="col-span-full flex justify-end gap-2">
              <Button size="sm" variant="ghost" onClick={() => setDraft(null)}>
                {t("panel.common.dismiss")}
              </Button>
              <Button
                size="sm"
                loading={save.isPending}
                disabled={!draft.panel_code}
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
