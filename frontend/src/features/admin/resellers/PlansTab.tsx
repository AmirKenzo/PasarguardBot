import { useEffect, useState } from "react";
import { AlertTriangle, History, Link2, Lock, Pencil, Plus, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";
import { Badge, Button, Card, EmptyState, ErrorState, Input, Skeleton } from "../../../components/ui";
import { panelResellersApi } from "../../../api/panel";
import { formatNumber, formatToman } from "../../../lib/format";
import type { PanelResellerPlanRow, PanelResellerPlanSaveRequest } from "../../../types/panel";
import { usePanelAction, usePanelQuery } from "../../../queries/usePanelApi";
import { ConfirmButton, FormModal, SelectField, Toggle } from "../components";
import { pricingLabels } from "./labels";
import {
  ADDON_DAYS,
  ADDON_PRICE_FIELDS,
  ADDON_USERS,
  ADDON_VOLUME,
  FIXED,
  HOURLY,
  LIVE_RATE_MODES,
  PER_TB,
  USAGE,
  isLegacyMode,
  normalizePlanDraft,
  ruleFor,
  validatePlanDraft,
} from "./planRules";
import type { AddonKey, PlanFieldErrors } from "./planRules";
import { PlanTypeGuide, PlanTypeTiles } from "./PlanTypeGuide";

const styleLabels = (t: TFunction): Record<string, string> => ({
  "": t("panel.common.default"),
  primary: t("panel.common.blue"),
  success: t("panel.common.green"),
  danger: t("panel.common.red"),
});

type Draft = Omit<PanelResellerPlanSaveRequest, "session_token" | "init_data"> & { linked: number };
type NumericKey =
  | "price"
  | "unit_price"
  | "data_limit_gb"
  | "duration"
  | "max_users"
  | "min_volume"
  | "max_volume"
  | "volume_step"
  | "addon_day_price"
  | "addon_gb_price"
  | "addon_user_price";

const EMPTY_DRAFT: Draft = {
  plan_id: null,
  panel_code: 0,
  pricing_mode: FIXED,
  price: 0,
  unit_price: 0,
  min_volume: 0,
  max_volume: 0,
  volume_step: 1,
  data_limit_gb: 0,
  max_users: 0,
  duration: 30,
  role_id: 0,
  enable: true,
  display_button_text: "",
  button_style: "",
  button_icon: "",
  notify_resellers: true,
  addon_day_price: 0,
  addon_gb_price: 0,
  addon_user_price: 0,
  linked: 0,
};

const INVALIDATE = [["reseller-plans"], ["reseller-overview"]];

const ADDON_LABEL_KEYS: Record<AddonKey, string> = {
  [ADDON_DAYS]: "days",
  [ADDON_VOLUME]: "volume",
  [ADDON_USERS]: "users",
};

function priceLine(t: TFunction, plan: PanelResellerPlanRow): string {
  switch (plan.pricing_mode) {
    case HOURLY:
      return t("panel.resellerHub.perHourAmount", { amount: formatToman(plan.unit_price) });
    case USAGE:
      return t("panel.resellerHub.perGbUsedAmount", { amount: formatToman(plan.unit_price) });
    case PER_TB:
      return t("panel.resellerHub.perTbAmount", { amount: formatToman(plan.unit_price) });
    default:
      return ruleFor(plan.pricing_mode).priceField === "price"
        ? formatToman(plan.price)
        : t("panel.resellerHub.perGbAmount", { amount: formatToman(plan.unit_price) });
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
    addon_day_price: plan.addon_day_price ?? 0,
    addon_gb_price: plan.addon_gb_price ?? 0,
    addon_user_price: plan.addon_user_price ?? 0,
    linked: plan.linked_accounts,
  };
}

/** A number box that keeps what is typed (e.g. "1.") and reports the parsed value. */
function NumberField({
  label,
  value,
  onChange,
  error,
  hint,
  placeholder,
  decimals = true,
}: {
  label: string;
  value: number | null | undefined;
  onChange: (value: number) => void;
  error?: string;
  hint?: string;
  placeholder?: string;
  decimals?: boolean;
}) {
  const [text, setText] = useState(value ? String(value) : "");
  useEffect(() => {
    // Follow outside changes (another plan opened) without fighting the user's typing.
    setText((current) => (Number(current || 0) === Number(value || 0) ? current : value ? String(value) : ""));
  }, [value]);

  return (
    <div>
      <Input
        label={label}
        inputMode={decimals ? "decimal" : "numeric"}
        value={text}
        placeholder={placeholder ?? "0"}
        error={error}
        onChange={(event) => {
          const cleaned = event.target.value
            .replace(/[٠-٩]/g, (digit) => String(digit.charCodeAt(0) - 0x0660))
            .replace(/[۰-۹]/g, (digit) => String(digit.charCodeAt(0) - 0x06f0))
            .replace(decimals ? /[^\d.]/g : /\D/g, "")
            .replace(/(\..*)\./g, "$1");
          setText(cleaned);
          onChange(Number(cleaned) || 0);
        }}
      />
      {hint && !error && <p className="mt-1 text-xs leading-5 text-muted">{hint}</p>}
    </div>
  );
}

export default function PlansTab() {
  const { t } = useTranslation();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [touched, setTouched] = useState<Set<string>>(new Set());
  const [submitted, setSubmitted] = useState(false);

  const query = usePanelQuery(["reseller-plans"], (auth) => panelResellersApi.listResellerPlans(auth));
  const save = usePanelAction(panelResellersApi.saveResellerPlan, { invalidate: INVALIDATE });
  const remove = usePanelAction(panelResellersApi.deleteResellerPlan, { invalidate: INVALIDATE });

  const panels = query.data?.panels || [];
  const plans = query.data?.plans || [];
  const byPanel = panels
    .map((panel) => ({ panel, plans: plans.filter((plan) => plan.panel_code === panel.code) }))
    .filter((group) => group.plans.length);

  const mode = draft?.pricing_mode || FIXED;
  const rule = ruleFor(mode);
  const legacy = isLegacyMode(mode);
  const locked = !!draft?.plan_id && (draft?.linked || 0) > 0;
  const rolePanel = draft?.panel_code ?? 0;
  const roles = usePanelQuery(
    ["reseller-roles", rolePanel],
    (auth) => panelResellersApi.listPanelRoles({ ...auth, panel_code: rolePanel }),
    { enabled: rolePanel > 0, retry: false, staleTime: 60_000 }
  );
  const editedPlan = plans.find((plan) => plan.id === draft?.plan_id);

  const roleOptions = (roles.data?.roles || []).map((role) => ({ value: String(role.id), label: role.name }));
  if (draft?.role_id && editedPlan?.role_id === draft.role_id && !roleOptions.some((o) => o.value === String(draft.role_id))) {
    roleOptions.push({ value: String(draft.role_id), label: editedPlan.role_name || `#${draft.role_id}` });
  }

  const errors: PlanFieldErrors = draft ? validatePlanDraft(t, draft, editedPlan?.pricing_mode ?? null) : {};
  const invalid = Object.keys(errors).length > 0;
  const errorFor = (key: keyof PlanFieldErrors) => (submitted || touched.has(key) ? errors[key] : undefined);

  const openDraft = (next: Draft) => {
    setDraft(next);
    setTouched(new Set());
    setSubmitted(false);
  };

  const field = (key: NumericKey, label: string, extra: { hint?: string; placeholder?: string; decimals?: boolean } = {}) =>
    draft && (
      <NumberField
        label={label}
        value={draft[key] as number | null | undefined}
        error={errorFor(key)}
        hint={extra.hint}
        placeholder={extra.placeholder}
        decimals={extra.decimals ?? true}
        onChange={(value) => {
          setDraft({ ...draft, [key]: value });
          setTouched((prev) => new Set(prev).add(key));
        }}
      />
    );

  // A price change on a live-rate plan bills every running account at the new rate right away.
  const priceChanged =
    !!editedPlan &&
    !!draft &&
    draft.linked > 0 &&
    Number(draft[rule.priceField] || 0) !== Number(editedPlan[rule.priceField] || 0) &&
    mode === editedPlan.pricing_mode;

  const submit = () => {
    if (!draft) return;
    setSubmitted(true);
    if (invalid) return;
    const { linked: _linked, ...body } = normalizePlanDraft(draft);
    save.mutate(body, { onSuccess: () => setDraft(null) });
  };

  const formHint = (key: string) => <p className="col-span-full -mt-1 text-xs leading-6 text-muted">{t(key)}</p>;

  return (
    <>
      <div className="mb-3 flex items-center justify-between gap-3">
        <p className="text-sm text-muted">{t("panel.resellerPlans.subtitle")}</p>
        <Button
          size="sm"
          disabled={!panels.length}
          onClick={() => openDraft({ ...EMPTY_DRAFT, panel_code: panels[0]?.code || 0 })}
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
                  <PlanCard
                    key={plan.id}
                    plan={plan}
                    onEdit={() => openDraft(toDraft(plan))}
                    onDelete={() => remove.mutate({ plan_id: plan.id })}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <FormModal
        open={draft !== null}
        onClose={() => setDraft(null)}
        size="xl"
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
            <div className="col-span-full">
              <SelectField
                label={t("panel.common.panel")}
                options={panels.map((panel) => ({ value: String(panel.code), label: panel.name }))}
                value={String(draft.panel_code)}
                disabled={locked}
                onChange={(event) => setDraft({ ...draft, panel_code: Number(event.target.value), role_id: 0 })}
              />
            </div>

            <div className="col-span-full space-y-2">
              <span className="block text-sm text-muted">{t("panel.resellerHub.planType")}</span>
              {legacy && (
                <p className="flex items-start gap-2 rounded-md bg-warning/10 px-3 py-2 text-xs leading-6 text-warning">
                  <History size={14} className="mt-1 shrink-0" />
                  {t(locked ? "panel.resellerHub.planForm.legacyLocked" : "panel.resellerHub.planForm.legacy", {
                    type: pricingLabels(t)[mode] || mode,
                  })}
                </p>
              )}
              {!(legacy && locked) && (
                <PlanTypeTiles
                  value={mode}
                  disabled={locked}
                  onChange={(next) => {
                    setDraft({ ...draft, pricing_mode: next });
                    setSubmitted(false);
                  }}
                />
              )}
              {errorFor("pricing_mode") && <p className="text-xs text-danger">{errors.pricing_mode}</p>}
              {!legacy && <PlanTypeGuide mode={mode} />}
            </div>

            <div className="col-span-full border-t border-border/60 pt-3 text-xs font-semibold text-muted">
              {t("panel.resellerHub.planForm.settingsSection")}
            </div>

            {mode === FIXED && (
              <>
                {field("price", t("panel.resellerHub.plans.price"), { decimals: false })}
                {field("data_limit_gb", t("panel.resellerHub.plans.dataLimit"), {
                  hint: t("panel.resellerHub.planForm.hint.fixedVolume"),
                })}
                {field("duration", t("panel.common.periodDays"), { decimals: false })}
              </>
            )}
            {mode === "unlimited" && (
              <>
                {field("price", t("panel.resellerHub.plans.price"), { decimals: false })}
                {field("duration", t("panel.common.periodDays"), { decimals: false })}
                {formHint("panel.resellerHub.planForm.hint.unlimitedVolume")}
              </>
            )}
            {mode === USAGE && (
              <>
                {field("unit_price", t("panel.resellerHub.plans.gbRate"), { decimals: false })}
                {field("data_limit_gb", t("panel.resellerHub.plans.totalTrafficCap"), {
                  hint: t("panel.resellerHub.planForm.hint.optionalCap"),
                  placeholder: t("panel.resellerHub.plans.zeroUnlimited"),
                })}
              </>
            )}
            {mode === HOURLY && (
              <>
                {field("unit_price", t("panel.resellerHub.plans.hourlyRate"), { decimals: false })}
                {field("data_limit_gb", t("panel.resellerHub.plans.totalTrafficCap"), {
                  hint: t("panel.resellerHub.planForm.hint.optionalCap"),
                  placeholder: t("panel.resellerHub.plans.zeroUnlimited"),
                })}
              </>
            )}
            {legacy && (
              <>
                {field(
                  "unit_price",
                  mode === PER_TB ? t("panel.resellerHub.plans.tbRate") : t("panel.resellerHub.plans.gbVolumeRate"),
                  { decimals: false }
                )}
                {field("data_limit_gb", t("panel.resellerHub.plans.dataLimit"), {
                  placeholder: t("panel.resellerHub.plans.zeroUnlimited"),
                })}
                {field("min_volume", t("panel.resellerPlans.minVolume"))}
                {field("max_volume", t("panel.resellerPlans.maxVolume"))}
                {field("volume_step", t("panel.resellerPlans.volumeStep"))}
                {field("duration", t("panel.common.periodDays"), {
                  decimals: false,
                  placeholder: t("panel.resellerHub.plans.zeroUnlimited"),
                })}
              </>
            )}
            {field("max_users", t("panel.resellerHub.plans.maxUsers"), {
              decimals: false,
              hint: t("panel.resellerHub.planForm.hint.maxUsers"),
              placeholder: t("panel.resellerHub.plans.zeroUnlimited"),
            })}

            {priceChanged && (
              <p
                className={`col-span-full flex items-start gap-2 rounded-md px-3 py-2 text-xs leading-6 ${
                  LIVE_RATE_MODES.has(mode) ? "bg-warning/10 text-warning" : "bg-surface-2 text-muted"
                }`}
              >
                <AlertTriangle size={14} className="mt-1 shrink-0" />
                {LIVE_RATE_MODES.has(mode)
                  ? t("panel.resellerHub.planForm.liveRateWarning", { count: formatNumber(draft.linked) })
                  : t("panel.resellerHub.planForm.futureRateNote")}
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
                onChange={(event) => {
                  setDraft({ ...draft, role_id: Number(event.target.value) });
                  setTouched((prev) => new Set(prev).add("role_id"));
                }}
              />
              <p className={`mt-1 text-xs ${roles.isError || errorFor("role_id") ? "text-danger" : "text-muted"}`}>
                {roles.isError ? roles.error.message : errorFor("role_id") || t("panel.resellerHub.plans.roleHint")}
              </p>
            </div>

            <div className="col-span-full border-t border-border/60 pt-3">
              <p className="text-xs font-semibold text-muted">{t("panel.resellerHub.planForm.addons.title")}</p>
              <p className="mt-0.5 text-xs leading-6 text-muted">{t("panel.resellerHub.planForm.addons.hint")}</p>
            </div>
            {rule.addons.map((addon) => {
              const name = ADDON_LABEL_KEYS[addon];
              return (
                <div key={addon}>
                  {field(ADDON_PRICE_FIELDS[addon], t(`panel.resellerHub.planForm.addons.${name}`), {
                    decimals: false,
                    hint: t(`panel.resellerHub.planForm.addons.${name}Hint`),
                    placeholder: t("panel.resellerHub.planForm.addons.off"),
                  })}
                </div>
              );
            })}

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
                hint={t("panel.resellerHub.planForm.hint.enable")}
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
            {submitted && invalid && (
              <p className="col-span-full rounded-md bg-danger/10 px-3 py-2 text-xs text-danger">
                {t("panel.resellerHub.planForm.fixErrors")}
              </p>
            )}
            <div className="col-span-full flex justify-end gap-2">
              <Button size="sm" variant="ghost" onClick={() => setDraft(null)}>
                {t("panel.common.dismiss")}
              </Button>
              <Button size="sm" loading={save.isPending} disabled={!draft.panel_code || (submitted && invalid)} onClick={submit}>
                {t("common.save")}
              </Button>
            </div>
          </div>
        )}
      </FormModal>
    </>
  );
}

function PlanCard({ plan, onEdit, onDelete }: { plan: PanelResellerPlanRow; onEdit: () => void; onDelete: () => void }) {
  const { t } = useTranslation();
  const rule = ruleFor(plan.pricing_mode);
  const addons = rule.addons
    .map((addon) => ({ addon, price: Number(plan[ADDON_PRICE_FIELDS[addon]] || 0) }))
    .filter((item) => item.price > 0);

  return (
    <Card className={`flex flex-col gap-3 p-4 ${plan.enable ? "" : "opacity-60"}`}>
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
        {isLegacyMode(plan.pricing_mode) && <Badge tone="warning">{t("panel.resellerHub.planForm.legacyBadge")}</Badge>}
        {plan.duration > 0 && <Badge tone="muted">{t("panel.plans.durationDays", { count: formatNumber(plan.duration) })}</Badge>}
        {plan.data_limit_gb > 0 ? (
          <Badge tone="muted">{formatNumber(plan.data_limit_gb)} GB</Badge>
        ) : (
          rule.volume !== "required" && <Badge tone="muted">{t("panel.resellerHub.planForm.unlimitedVolume")}</Badge>
        )}
        <Badge tone="muted">
          {plan.max_users > 0
            ? t("panel.resellerHub.plans.users", { count: formatNumber(plan.max_users) })
            : t("panel.resellerHub.planForm.unlimitedUsers")}
        </Badge>
        {plan.role_name && <Badge tone="muted">{plan.role_name}</Badge>}
      </div>
      {addons.length > 0 && (
        <div className="flex flex-wrap gap-1.5 text-[11px]">
          {addons.map(({ addon, price }) => (
            <Badge key={addon} tone="primary">
              {t(`panel.resellerHub.planForm.addonBadge.${ADDON_LABEL_KEYS[addon]}`, { amount: formatToman(price) })}
            </Badge>
          ))}
        </div>
      )}
      <div className="mt-auto flex items-center justify-between gap-2 border-t border-border/60 pt-3">
        <span className="flex items-center gap-1 text-xs text-muted">
          <Link2 size={12} />
          {t("panel.resellerHub.plans.linked", { count: formatNumber(plan.linked_accounts) })}
        </span>
        <div className="flex gap-1">
          <Button size="sm" variant="ghost" onClick={onEdit}>
            <Pencil size={14} />
          </Button>
          {plan.linked_accounts === 0 && (
            <ConfirmButton size="sm" variant="ghost" message={t("panel.resellerPlans.deleteConfirm")} onConfirm={onDelete}>
              <Trash2 size={14} className="text-danger" />
            </ConfirmButton>
          )}
        </div>
      </div>
    </Card>
  );
}
