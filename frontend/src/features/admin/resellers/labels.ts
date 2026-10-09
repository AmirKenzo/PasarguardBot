import type { TFunction } from "i18next";
import { formatNumber } from "../../../lib/format";

export const GB = 1024 ** 3;

export type Tone = "primary" | "success" | "warning" | "danger" | "muted";

export const statusLabels = (t: TFunction): Record<string, string> => ({
  active: t("panel.resellerHub.status.active"),
  paused: t("panel.resellerHub.status.paused"),
  suspended: t("panel.resellerHub.status.suspended"),
  usage_capped: t("panel.resellerHub.status.usage_capped"),
  admin_paused: t("panel.resellerHub.status.admin_paused"),
  expired: t("panel.resellerHub.status.expired"),
});

export const STATUS_TONE: Record<string, Tone> = {
  active: "success",
  paused: "muted",
  suspended: "warning",
  usage_capped: "warning",
  admin_paused: "danger",
  expired: "danger",
};

export const pricingLabels = (t: TFunction): Record<string, string> => ({
  fixed: t("panel.common.flatRate"),
  per_gb: t("panel.common.perGigabyte"),
  per_tb: t("panel.common.perTerabyte"),
  hourly: t("panel.common.hourly"),
  usage: t("panel.common.metered"),
});

export const eventLabels = (t: TFunction): Record<string, string> => ({
  purchase: t("panel.resellerHub.event.purchase"),
  import: t("panel.resellerHub.event.import"),
  renew: t("panel.resellerHub.event.renew"),
  extend: t("panel.resellerHub.event.extend"),
  capacity: t("panel.resellerHub.event.capacity"),
  max_users: t("panel.resellerHub.event.max_users"),
  pause: t("panel.resellerHub.event.pause"),
  resume: t("panel.resellerHub.event.resume"),
  admin_pause: t("panel.resellerHub.event.admin_pause"),
  admin_resume: t("panel.resellerHub.event.admin_resume"),
  suspend: t("panel.resellerHub.event.suspend"),
  reactivate: t("panel.resellerHub.event.reactivate"),
  usage_cap_set: t("panel.resellerHub.event.usage_cap_set"),
  usage_cap_hit: t("panel.resellerHub.event.usage_cap_hit"),
  password: t("panel.resellerHub.event.password"),
  low_balance: t("panel.resellerHub.event.low_balance"),
  price_change: t("panel.resellerHub.event.price_change"),
  expire: t("panel.resellerHub.event.expire"),
  purge: t("panel.resellerHub.event.purge"),
  delete: t("panel.resellerHub.event.delete"),
});

export const EVENT_TONE: Record<string, Tone> = {
  purchase: "success",
  import: "primary",
  renew: "success",
  extend: "success",
  capacity: "primary",
  max_users: "primary",
  pause: "muted",
  resume: "success",
  admin_pause: "danger",
  admin_resume: "success",
  suspend: "danger",
  reactivate: "success",
  usage_cap_set: "primary",
  usage_cap_hit: "warning",
  password: "muted",
  low_balance: "warning",
  price_change: "warning",
  expire: "danger",
  purge: "danger",
  delete: "danger",
};

/** Hours of wallet left, in the largest readable unit. */
export function formatRunway(t: TFunction, hours: number | null | undefined): string {
  if (hours === null || hours === undefined) return "—";
  if (hours < 1) return t("panel.resellerHub.runwayMinutes", { count: formatNumber(Math.max(1, Math.round(hours * 60))) });
  if (hours < 48) return t("panel.resellerHub.runwayHours", { count: formatNumber(Math.round(hours)) });
  return t("panel.resellerHub.runwayDays", { count: formatNumber(Math.round(hours / 24)) });
}

export function runwayTone(hours: number | null | undefined, warnHours: number): Tone {
  if (hours === null || hours === undefined) return "muted";
  if (hours < Math.min(6, warnHours)) return "danger";
  if (hours < warnHours) return "warning";
  return "success";
}

/** The amount of an event's payload that left the wallet, if any. */
export function eventAmount(data: Record<string, unknown>): number {
  const value = Number(data.amount ?? data.charge ?? 0);
  return Number.isFinite(value) && value > 0 ? value : 0;
}
