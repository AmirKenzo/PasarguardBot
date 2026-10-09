import { useState } from "react";
import { Link2, Lock, Pencil, Plus, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";
import { Badge, Button, Card, EmptyState, ErrorState, Input, Skeleton } from "../../../components/ui";
import { panelResellersApi } from "../../../api/panel";
import { formatNumber, formatToman } from "../../../lib/format";
import type { PanelResellerPlanRow, PanelResellerPlanSaveRequest } from "../../../types/panel";
import { usePanelAction, usePanelQuery } from "../../../queries/usePanelApi";
import { ConfirmButton, FormModal, SelectField, Toggle } from "../components";
import { pricingLabels } from "./labels";

const styleLabels = (t: TFunction): Record<string, string> => ({
  "": t("panel.common.default"),
  primary: t("panel.common.blue"),
  success: t("panel.common.green"),
  danger: t("panel.common.red"),
});

type Draft = Omit<PanelResellerPlanSaveRequest, "session_token" | "init_data"> & { linked: number };

const EMPTY_DRAFT: Draft = {
  plan_id: null,
  panel_code: 0,
  pricing_mode: "fixed",
  price: 0,
  unit_price: 0,
  min_volume: 0,
  max_volume: 0,
  volume_step: 1,
  data_limit_gb: 0,
  max_users: 0,
  duration: 0,
  role_id: 0,
  enable: true,
  display_button_text: "",
  button_style: "",
  button_icon: "",
  notify_resellers: true,
  linked: 0,
};

const LIVE_RATE_MODES = new Set(["hourly", "usage"]);
const INVALIDATE = [["reseller-plans"], ["reseller-overview"]];

function priceLine(t: TFunction, plan: PanelResellerPlanRow): string {
  switch (plan.pricing_mode) {
    case "fixed":
      return formatToman(plan.price);
    case "hourly":
      return t("panel.resellerHub.perHourAmount", { amount: formatToman(plan.unit_price) });
    case "per_tb":
      return t("panel.resellerHub.perTbAmount", { amount: formatToman(plan.unit_price) });
    case "usage":
      return t("panel.resellerHub.perGbUsedAmount", { amount: formatToman(plan.unit_price) });
    default:
      return t("panel.resellerHub.perGbAmount", { amount: formatToman(plan.unit_price) });
  }
}

function toDraft(plan: PanelResellerPlanRow): Draft {
  return {
    plan_id: plan.id,
    panel_code: plan.panel_code,
    pricing_mode: plan.pricing_mode,
    price: plan.price,
    unit_price: plan.unit_price,
    min_volume: plan.min_volume,
    max_volume: plan.max_volume,
    volume_step: plan.volume_step,
    data_limit_gb: plan.data_limit_gb,
    max_users: plan.max_users,
    duration: plan.duration,
    role_id: plan.role_id,
    enable: plan.enable,
    display_button_text: plan.display_button_text || "",
    button_style: plan.button_style || "",
    button_icon: plan.button_icon ? String(plan.button_icon) : "",
    notify_resellers: true,
    linked: plan.linked_accounts,
  };
}

export default function PlansTab() {
  const { t } = useTranslation();
  const [draft, setDraft] = useState<Draft | null>(null);

  const query = usePanelQuery(["reseller-plans"], (auth) => panelResellersApi.listResellerPlans(auth));
  const save = usePanelAction(panelResellersApi.saveResellerPlan, { invalidate: INVALIDATE });
  const remove = usePanelAction(panelResellersApi.deleteResellerPlan, { invalidate: INVALIDATE });

  const panels = query.data?.panels || [];
  const plans = query.data?.plans || [];
  const byPanel = panels
    .map((panel) => ({ panel, plans: plans.filter((plan) => plan.panel_code === panel.code) }))
    .filter((group) => group.plans.length);

  function numberField(label: string, key: keyof Draft, hint?: string) {
    if (!draft) return null;
    return (
      <Input
        label={label}
        inputMode="decimal"
        value={String(draft[key] ?? 0)}
        onChange={(event) => setDraft({ ...draft, [key]: Number(event.target.value.replace(/,/g, "")) || 0 })}
        {...(hint ? { placeholder: hint } : {})}
      />
    );
  }

  const mode = draft?.pricing_mode || "fixed";
  const locked = !!draft?.plan_id && (draft?.linked || 0) > 0;
  const rolePanel = draft?.panel_code ?? 0;
  const roles = usePanelQuery(
    ["reseller-roles", rolePanel],
    (auth) => panelResellersApi.listPanelRoles({ ...auth, panel_code: rolePanel }),
    { enabled: rolePanel > 0, retry: false, staleTime: 60_000 }
  );
  const editedPlan = plans.find((plan) => plan.id === draft?.plan_id);

  // New plans are fixed or usage; an older plan of another type keeps its own type while edited.
  const typeOptions = [...(query.data?.pricing_modes || [])];
  if (draft && !typeOptions.includes(mode)) typeOptions.push(mode);

  const roleOptions = (roles.data?.roles || []).map((role) => ({ value: String(role.id), label: role.name }));
  if (draft?.role_id && editedPlan?.role_id === draft.role_id && !roleOptions.some((o) => o.value === String(draft.role_id))) {
    roleOptions.push({ value: String(draft.role_id), label: editedPlan.role_name || `#${draft.role_id}` });
  }

  return (
    <>
      <div className="mb-3 flex items-center justify-between gap-3">
        <p className="text-sm text-muted">{t("panel.resellerPlans.subtitle")}</p>
        <Button
          size="sm"
          disabled={!panels.length}
          onClick={() => setDraft({ ...EMPTY_DRAFT, panel_code: panels[0]?.code || 0 })}
        >
          <Plus size={16} />
          {t("panel.common.addPlan")}
        </Button>
      </div>

      {query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : query.isLoading ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-36 w-full" />
          ))}
        </div>
      ) : !byPanel.length ? (
        <Card className="p-4">
          <EmptyState
            title={t("panel.common.noPlansDefined")}
            description={panels.length ? undefined : t("panel.common.addPanelFirst")}
          />
        </Card>
      ) : (
        <div className="space-y-5">
          {byPanel.map(({ panel, plans: panelPlans }) => (
            <div key={panel.code}>
              <h3 className="mb-2 text-xs font-semibold text-muted">{panel.name}</h3>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {panelPlans.map((plan) => (
                  <Card key={plan.id} className={`flex flex-col gap-3 p-4 ${plan.enable ? "" : "opacity-60"}`}>
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-text">
                          {plan.display_button_text?.split("\n")[0] || `${t("panel.resellerHub.plans.plan")} #${plan.id}`}
                        </p>
                        <p className="mt-0.5 text-xs text-muted">{pricingLabels(t)[plan.pricing_mode] || plan.pricing_mode}</p>
                      </div>
                      {plan.enable ? (
                        <Badge tone="success">{t("panel.common.active")}</Badge>
                      ) : (
                        <Badge tone="muted">{t("panel.common.inactive")}</Badge>
                      )}
                    </div>
                    <p className="text-lg font-bold text-primary">{priceLine(t, plan)}</p>
                    <div className="flex flex-wrap gap-1.5 text-[11px]">
                      {plan.duration > 0 && <Badge tone="muted">{t("panel.plans.durationDays", { count: formatNumber(plan.duration) })}</Badge>}
                      {plan.data_limit_gb > 0 && <Badge tone="muted">{formatNumber(plan.data_limit_gb)} GB</Badge>}
                      {plan.max_users > 0 && (
                        <Badge tone="muted">{t("panel.resellerHub.plans.users", { count: formatNumber(plan.max_users) })}</Badge>
                      )}
                      {plan.role_name && <Badge tone="muted">{plan.role_name}</Badge>}
                    </div>
                    <div className="mt-auto flex items-center justify-between gap-2 border-t border-border/60 pt-3">
                      <span className="flex items-center gap-1 text-xs text-muted">
                        <Link2 size={12} />
                        {t("panel.resellerHub.plans.linked", { count: formatNumber(plan.linked_accounts) })}
                      </span>
                      <div className="flex gap-1">
                        <Button size="sm" variant="ghost" onClick={() => setDraft(toDraft(plan))}>
                          <Pencil size={14} />
                        </Button>
                        {plan.linked_accounts === 0 && (
                          <ConfirmButton
                            size="sm"
                            variant="ghost"
                            message={t("panel.resellerPlans.deleteConfirm")}
                            onConfirm={() => remove.mutate({ plan_id: plan.id })}
                          >
                            <Trash2 size={14} className="text-danger" />
                          </ConfirmButton>
                        )}
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <FormModal
        open={draft !== null}
        onClose={() => setDraft(null)}
        title={draft?.plan_id ? t("panel.resellerPlans.editTitle", { id: draft.plan_id }) : t("panel.common.addResellerPlan")}
      >
        {draft && (
          <div className="grid gap-3 sm:grid-cols-2">
            {locked && (
              <p className="col-span-full flex items-start gap-2 rounded-md bg-surface-2 px-3 py-2 text-xs text-muted">
                <Lock size={13} className="mt-0.5 shrink-0" />
                {t("panel.resellerHub.plans.lockedHint", { count: formatNumber(draft.linked) })}
              </p>
            )}
            <SelectField
              label={t("panel.common.panel")}
              options={panels.map((panel) => ({ value: String(panel.code), label: panel.name }))}
              value={String(draft.panel_code)}
              disabled={locked}
              onChange={(event) => setDraft({ ...draft, panel_code: Number(event.target.value), role_id: 0 })}
            />
            <SelectField
              label={t("panel.resellerHub.planType")}
              options={typeOptions.map((value) => ({ value, label: pricingLabels(t)[value] || value }))}
              value={mode}
              disabled={locked}
              onChange={(event) => {
                const next = event.target.value;
                // A usage plan has no up-front price and no duration.
                setDraft(next === "usage" ? { ...draft, pricing_mode: next, price: 0, duration: 0 } : { ...draft, pricing_mode: next });
              }}
            />
            {(mode === "fixed" || mode === "usage") && (
              <p className="col-span-full -mt-1 text-xs leading-6 text-muted">
                {t(mode === "fixed" ? "panel.resellerHub.plans.fixedHint" : "panel.resellerHub.plans.usageHint")}
              </p>
            )}

            <div className="col-span-full">
              <SelectField
                label={t("panel.resellerHub.plans.role")}
                options={[
                  {
                    value: "0",
                    label: roles.isLoading ? t("panel.resellerHub.plans.rolesLoading") : t("panel.resellerHub.plans.chooseRole"),
                  },
                  ...roleOptions,
                ]}
                value={String(draft.role_id || 0)}
                disabled={roles.isLoading || roleOptions.length === 0}
                onChange={(event) => setDraft({ ...draft, role_id: Number(event.target.value) })}
              />
              <p className={`mt-1 text-xs ${roles.isError ? "text-danger" : "text-muted"}`}>
                {roles.isError ? roles.error.message : t("panel.resellerHub.plans.roleHint")}
              </p>
            </div>

            {mode === "fixed" && numberField(t("panel.resellerHub.plans.price"), "price")}
            {mode === "usage" && numberField(t("panel.resellerHub.plans.gbRate"), "unit_price")}
            {mode === "hourly" && numberField(t("panel.resellerHub.plans.hourlyRate"), "unit_price")}
            {mode === "per_gb" && numberField(t("panel.resellerHub.plans.gbVolumeRate"), "unit_price")}
            {mode === "per_tb" && numberField(t("panel.resellerHub.plans.tbRate"), "unit_price")}
            {numberField(
              mode === "usage" ? t("panel.resellerHub.plans.totalTrafficCap") : t("panel.resellerHub.plans.dataLimit"),
              "data_limit_gb",
              t("panel.resellerHub.plans.zeroUnlimited")
            )}
            {(mode === "per_gb" || mode === "per_tb") && (
              <>
                {numberField(t("panel.resellerPlans.minVolume"), "min_volume")}
                {numberField(t("panel.resellerPlans.maxVolume"), "max_volume")}
                {numberField(t("panel.resellerPlans.volumeStep"), "volume_step")}
              </>
            )}
            {mode !== "usage" &&
              numberField(t("panel.common.periodDays"), "duration", t("panel.resellerHub.plans.zeroUnlimited"))}
            {numberField(t("panel.resellerHub.plans.maxUsers"), "max_users", t("panel.resellerHub.plans.zeroUnlimited"))}

            <div className="col-span-full border-t border-border/60 pt-3 text-xs font-semibold text-muted">
              {t("panel.resellerHub.plans.buttonSection")}
            </div>
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
            <div className="col-span-full space-y-1">
              <Toggle
                checked={draft.enable ?? true}
                onChange={(enable) => setDraft({ ...draft, enable })}
                label={t("panel.resellerPlans.enabled")}
              />
              {locked && LIVE_RATE_MODES.has(mode) && (
                <Toggle
                  checked={draft.notify_resellers ?? true}
                  onChange={(notify_resellers) => setDraft({ ...draft, notify_resellers })}
                  label={t("panel.resellerHub.plans.notify")}
                  hint={t("panel.resellerHub.plans.notifyHint")}
                />
              )}
            </div>
            <div className="col-span-full flex justify-end gap-2">
              <Button size="sm" variant="ghost" onClick={() => setDraft(null)}>
                {t("panel.common.dismiss")}
              </Button>
              <Button
                size="sm"
                loading={save.isPending}
                disabled={!draft.panel_code || !draft.role_id}
                onClick={() => {
                  const { linked: _linked, ...body } = draft;
                  save.mutate(body, { onSuccess: () => setDraft(null) });
                }}
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
