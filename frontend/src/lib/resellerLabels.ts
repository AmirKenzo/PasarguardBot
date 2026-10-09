/** Reseller labels shared by the user web app and the admin panel. */
import type { TFunction } from "i18next";
import { formatNumber } from "./format";

export type ResellerTone = "primary" | "success" | "warning" | "danger" | "muted";

export const RESELLER_STATUS_KEYS = ["active", "paused", "suspended", "usage_capped", "admin_paused", "expired"] as const;

export const RESELLER_EVENT_KEYS = [
  "purchase",
  "import",
  "renew",
  "extend",
  "capacity",
  "max_users",
  "pause",
  "resume",
  "admin_pause",
  "admin_resume",
  "suspend",
  "reactivate",
  "usage_cap_set",
  "usage_cap_hit",
  "password",
  "low_balance",
  "price_change",
  "expire",
  "purge",
  "delete",
] as const;

export const statusLabels = (t: TFunction): Record<string, string> =>
  Object.fromEntries(RESELLER_STATUS_KEYS.map((key) => [key, t(`reseller.status.${key}`)]));

export const eventLabels = (t: TFunction): Record<string, string> =>
  Object.fromEntries(RESELLER_EVENT_KEYS.map((key) => [key, t(`reseller.event.${key}`)]));

export const STATUS_TONE: Record<string, ResellerTone> = {
  active: "success",
  paused: "muted",
  suspended: "warning",
  usage_capped: "warning",
  admin_paused: "danger",
  expired: "danger",
};

export const EVENT_TONE: Record<string, ResellerTone> = {
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
  if (hours < 1) return t("reseller.runwayMinutes", { count: formatNumber(Math.max(1, Math.round(hours * 60))) });
  if (hours < 48) return t("reseller.runwayHours", { count: formatNumber(Math.round(hours)) });
  return t("reseller.runwayDays", { count: formatNumber(Math.round(hours / 24)) });
}

export function runwayTone(hours: number | null | undefined, warnHours: number): ResellerTone {
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

export function resellerModeLabel(t: TFunction, mode: string): string {
  return ["fixed", "per_gb", "per_tb", "hourly", "usage"].includes(mode) ? t(`reseller.mode.${mode}`) : mode;
}
