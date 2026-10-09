import type { TFunction } from "i18next";

export {
  EVENT_TONE,
  STATUS_TONE,
  eventAmount,
  eventLabels,
  formatRunway,
  runwayTone,
  statusLabels,
} from "../../../lib/resellerLabels";
export type { ResellerTone as Tone } from "../../../lib/resellerLabels";

export const GB = 1024 ** 3;

export const pricingLabels = (t: TFunction): Record<string, string> => ({
  fixed: t("panel.common.flatRate"),
  per_gb: t("panel.common.perGigabyte"),
  per_tb: t("panel.common.perTerabyte"),
  hourly: t("panel.common.hourly"),
  usage: t("panel.common.metered"),
});
