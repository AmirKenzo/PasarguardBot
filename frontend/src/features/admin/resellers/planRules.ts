/**
 * Reseller plan rules for the admin plan form.
 * Mirrors app/services/reseller/plan_rules.py (RULES, validate_plan, normalize_plan); keep both in step.
 */
import type { TFunction } from "i18next";

export const FIXED = "fixed";
export const UNLIMITED = "unlimited";
export const USAGE = "usage";
export const HOURLY = "hourly";
export const PER_GB = "per_gb";
export const PER_TB = "per_tb";

export const CREATABLE_MODES = [FIXED, UNLIMITED, USAGE, HOURLY] as const;
export const LEGACY_MODES = [PER_GB, PER_TB] as const;
/** Plans whose price change applies to running accounts at once (billed from the live plan). */
export const LIVE_RATE_MODES: ReadonlySet<string> = new Set([HOURLY, USAGE]);

export const ADDON_DAYS = "extra_days";
export const ADDON_VOLUME = "extra_volume";
export const ADDON_USERS = "buy_user_capacity";
export type AddonKey = typeof ADDON_DAYS | typeof ADDON_VOLUME | typeof ADDON_USERS;
export type AddonPriceField = "addon_day_price" | "addon_gb_price" | "addon_user_price";

export const ADDON_PRICE_FIELDS: Record<AddonKey, AddonPriceField> = {
  [ADDON_DAYS]: "addon_day_price",
  [ADDON_VOLUME]: "addon_gb_price",
  [ADDON_USERS]: "addon_user_price",
};

export interface PlanRule {
  mode: string;
  /** Price the buyer pays: the package `price` or the per GB / per hour `unit_price`. */
  priceField: "price" | "unit_price";
  volume: "required" | "none" | "optional";
  duration: "required" | "none" | "optional";
  renewable: boolean;
  addons: AddonKey[];
  usageCap: boolean;
  needsWallet: boolean;
}

export const PLAN_RULES: Record<string, PlanRule> = {
  [FIXED]: {
    mode: FIXED,
    priceField: "price",
    volume: "required",
    duration: "required",
    renewable: true,
    addons: [ADDON_DAYS, ADDON_VOLUME, ADDON_USERS],
    usageCap: false,
    needsWallet: false,
  },
  [UNLIMITED]: {
    mode: UNLIMITED,
    priceField: "price",
    volume: "none",
    duration: "required",
    renewable: true,
    addons: [ADDON_DAYS, ADDON_USERS],
    usageCap: false,
    needsWallet: false,
  },
  [USAGE]: {
    mode: USAGE,
    priceField: "unit_price",
    volume: "optional",
    duration: "none",
    renewable: false,
    addons: [ADDON_USERS],
    usageCap: true,
    needsWallet: true,
  },
  [HOURLY]: {
    mode: HOURLY,
    priceField: "unit_price",
    volume: "optional",
    duration: "none",
    renewable: false,
    addons: [ADDON_USERS],
    usageCap: false,
    needsWallet: true,
  },
  [PER_GB]: {
    mode: PER_GB,
    priceField: "unit_price",
    volume: "optional",
    duration: "optional",
    renewable: false,
    addons: [ADDON_USERS],
    usageCap: false,
    needsWallet: false,
  },
  [PER_TB]: {
    mode: PER_TB,
    priceField: "unit_price",
    volume: "optional",
    duration: "optional",
    renewable: false,
    addons: [ADDON_USERS],
    usageCap: false,
    needsWallet: false,
  },
};

export function ruleFor(mode: string | null | undefined): PlanRule {
  return PLAN_RULES[mode || FIXED] ?? (PLAN_RULES[FIXED] as PlanRule);
}

export const isLegacyMode = (mode: string) => (LEGACY_MODES as readonly string[]).includes(mode);

/** The plan form fields `validatePlanDraft` checks. */
export interface PlanDraftValues {
  pricing_mode?: string;
  price?: number;
  unit_price?: number;
  data_limit_gb?: number | null;
  duration?: number;
  max_users?: number;
  min_volume?: number;
  max_volume?: number;
  volume_step?: number;
  role_id: number;
  addon_day_price?: number;
  addon_gb_price?: number;
  addon_user_price?: number;
}

export type PlanFieldErrors = Partial<Record<keyof PlanDraftValues, string>>;

/** Per-field errors for the plan form; empty when the plan can be saved. */
export function validatePlanDraft(
  t: TFunction,
  draft: PlanDraftValues,
  existingMode: string | null = null
): PlanFieldErrors {
  const errors: PlanFieldErrors = {};
  const mode = draft.pricing_mode || FIXED;
  const known = mode in PLAN_RULES;
  if (!known || (isLegacyMode(mode) && mode !== existingMode)) {
    errors.pricing_mode = t("panel.resellerHub.planForm.errors.type");
    return errors;
  }
  const rule = ruleFor(mode);
  const key = "panel.resellerHub.planForm.errors";

  if (Number(draft[rule.priceField] || 0) <= 0) {
    errors[rule.priceField] = t(`${key}.price.${mode}`);
  }
  if (rule.volume === "required" && Number(draft.data_limit_gb || 0) <= 0) {
    errors.data_limit_gb = t(`${key}.volumeRequired`);
  }
  if (Number(draft.data_limit_gb || 0) < 0) errors.data_limit_gb = t(`${key}.negative`);
  if (rule.duration === "required" && Number(draft.duration || 0) <= 0) {
    errors.duration = t(`${key}.durationRequired`);
  }
  if (Number(draft.max_users || 0) < 0) errors.max_users = t(`${key}.negative`);
  for (const field of Object.values(ADDON_PRICE_FIELDS)) {
    if (Number(draft[field] || 0) < 0) errors[field] = t(`${key}.negative`);
  }
  if (isLegacyMode(mode)) {
    const max = Number(draft.max_volume || 0);
    if (max && max < Number(draft.min_volume || 0)) errors.max_volume = t(`${key}.maxBelowMin`);
    if (Number(draft.volume_step || 0) <= 0) errors.volume_step = t(`${key}.volumeStep`);
  }
  if (!draft.role_id) errors.role_id = t(`${key}.role`);
  return errors;
}

/** Clears what the type does not use, like `normalize_plan` on the server, so the request is honest. */
export function normalizePlanDraft<T extends PlanDraftValues>(draft: T): T {
  const rule = ruleFor(draft.pricing_mode);
  const out: T = { ...draft };
  if (rule.volume === "none") out.data_limit_gb = 0;
  if (rule.duration === "none") out.duration = 0;
  if (rule.priceField === "unit_price") out.price = 0;
  else out.unit_price = 0;
  for (const [addon, field] of Object.entries(ADDON_PRICE_FIELDS) as [AddonKey, AddonPriceField][]) {
    if (!rule.addons.includes(addon)) out[field] = 0;
  }
  return out;
}
