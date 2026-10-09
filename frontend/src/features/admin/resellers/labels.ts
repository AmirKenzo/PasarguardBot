import type { TFunction } from "i18next";
import { EVENT_TONE as SHARED_EVENT_TONE, eventLabels as sharedEventLabels } from "../../../lib/resellerLabels";
import type { ResellerTone } from "../../../lib/resellerLabels";

export {
  STATUS_TONE,
  eventAmount,
  formatRunway,
  runwayTone,
  statusLabels,
} from "../../../lib/resellerLabels";
export type { ResellerTone as Tone } from "../../../lib/resellerLabels";

export const GB = 1024 ** 3;

/** Every plan type the admin hub can meet: the four sold today, then the legacy ones. */
export const ALL_PLAN_MODES = ["fixed", "unlimited", "usage", "hourly", "per_gb", "per_tb"] as const;

/** Event kinds added with the plan add-ons and admin repair tools. */
const ADMIN_EVENT_KEYS = ["extra_days", "extra_volume", "data_limit", "plan_change", "panel_sync", "usage_forgiven"] as const;

const ADMIN_EVENT_TONE: Record<string, ResellerTone> = {
  extra_days: "success",
  extra_volume: "success",
  data_limit: "primary",
  plan_change: "primary",
  panel_sync: "muted",
  usage_forgiven: "warning",
};

export const EVENT_TONE: Record<string, ResellerTone> = { ...SHARED_EVENT_TONE, ...ADMIN_EVENT_TONE };

export const eventLabels = (t: TFunction): Record<string, string> => ({
  ...sharedEventLabels(t),
  ...Object.fromEntries(ADMIN_EVENT_KEYS.map((key) => [key, t(`panel.resellerHub.events.${key}`)])),
});

/** Full plan type names, e.g. «مصرفی (بر اساس حجم مصرف)»; the same wording as the bot and the web app. */
export const pricingLabels = (t: TFunction): Record<string, string> =>
  Object.fromEntries(ALL_PLAN_MODES.map((mode) => [mode, t(`panel.resellerHub.modes.${mode}`)]));

/** Short plan type names («ثابت», «نامحدود», «مصرفی», «ساعتی») for badges and tight spots. */
export const pricingShortLabels = (t: TFunction): Record<string, string> =>
  Object.fromEntries(ALL_PLAN_MODES.map((mode) => [mode, t(`panel.resellerHub.modesShort.${mode}`)]));
