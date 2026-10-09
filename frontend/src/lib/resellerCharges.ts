/** How one reseller charge came about: usage × rate over a period. Shared by the web app and the admin panel. */
import type { TFunction } from "i18next";
import i18n from "../i18n";
import { formatNumber, formatToman } from "./format";

const GB = 1024 ** 3;

export interface ChargeLike {
  kind: string;
  used_bytes?: number | null;
  billed_minutes?: number | null;
  unit_price?: number | null;
  rate_estimated?: boolean;
  period_start?: number | null;
  charged_at?: number | null;
}

function gigabytes(bytes: number): string {
  const value = bytes / GB;
  const digits = value >= 100 ? 1 : value >= 1 ? 2 : 3;
  return formatNumber(Number(value.toFixed(digits)));
}

/** What was consumed: traffic in GB for usage charges, minutes for hourly ones. */
export function chargeUsage(t: TFunction, charge: ChargeLike): string {
  if (charge.kind === "hourly") return t("reseller.charge.minutes", { count: formatNumber(charge.billed_minutes ?? 0) });
  return t("reseller.charge.gigabytes", { value: gigabytes(charge.used_bytes ?? 0) });
}

/** The rate applied; "≈" marks rates rebuilt from amount ÷ usage for old rows. */
export function chargeRate(t: TFunction, charge: ChargeLike): string {
  if (charge.unit_price == null) return "—";
  const amount = formatToman(charge.unit_price);
  const text =
    charge.kind === "hourly" ? t("reseller.perHour", { amount }) : t("reseller.perGb", { amount });
  return charge.rate_estimated ? `≈ ${text}` : text;
}

/** "usage × rate", e.g. "1.25 GB × 2,500 Toman". */
export function chargeFormula(t: TFunction, charge: ChargeLike): string {
  if (charge.unit_price == null) return chargeUsage(t, charge);
  const rate = formatToman(charge.unit_price);
  if (charge.kind === "hourly") {
    return t("reseller.charge.hourlyFormula", {
      minutes: formatNumber(charge.billed_minutes ?? 0),
      rate,
    });
  }
  return t("reseller.charge.usageFormula", { value: gigabytes(charge.used_bytes ?? 0), rate });
}

function clock(unix: number): string {
  return new Intl.DateTimeFormat(i18n.language === "fa" ? "fa-IR" : "en-US", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(unix * 1000));
}

function dayAndClock(unix: number): string {
  return new Intl.DateTimeFormat(i18n.language === "fa" ? "fa-IR-u-ca-persian" : "en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(unix * 1000));
}

/** The charged period: "12:00 – 13:00" on one day, full dates across days, or just the charge time. */
export function chargePeriod(t: TFunction, charge: ChargeLike): string {
  const end = charge.charged_at ?? 0;
  if (charge.kind === "hourly" && end) {
    return t("reseller.charge.hourOf", { from: dayAndClock(end), to: clock(end + 3600) });
  }
  const start = charge.period_start;
  if (!start || !end) return end ? dayAndClock(end) : "—";
  const sameDay = new Date(start * 1000).toDateString() === new Date(end * 1000).toDateString();
  return sameDay ? `${dayAndClock(start)} – ${clock(end)}` : `${dayAndClock(start)} – ${dayAndClock(end)}`;
}
