/** Locale-aware formatting for numbers, currency, byte sizes, and dates.
 * Renders in Persian (with the Jalali calendar) or English depending on the
 * user's selected language, using the raw numeric/timestamp fields the backend
 * sends alongside its own Persian-formatted strings (which the frontend ignores). */

import i18n from "../i18n";

function isFa(): boolean {
  return (i18n.language || "fa") === "fa";
}

function numberFormatter(): Intl.NumberFormat {
  return new Intl.NumberFormat(isFa() ? "fa-IR" : "en-US");
}

export function formatToman(amount: number): string {
  const value = numberFormatter().format(Math.round(amount));
  return `${value} ${i18n.t("common.toman")}`;
}

export function formatNumber(value: number): string {
  return numberFormatter().format(value);
}

export function formatUnixDate(unixSeconds: number): string {
  if (!unixSeconds) return i18n.t("common.unknown");
  const date = new Date(unixSeconds * 1000);
  const formatter = new Intl.DateTimeFormat(isFa() ? "fa-IR-u-ca-persian" : "en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
  return formatter.format(date);
}

/** Bilingual byte-size formatting, mirroring the backend's format_size thresholds. */
export function formatBytes(sizeBytes: number | null | undefined, decimalPlaces = 0): string {
  if (sizeBytes === null || sizeBytes === undefined) return i18n.t("common.unknown");
  const t = i18n.t.bind(i18n);
  if (sizeBytes < 0) return `-${formatBytes(Math.abs(sizeBytes), decimalPlaces)}`;

  const n = numberFormatter();
  if (sizeBytes < 1024) return `${n.format(sizeBytes)} ${t("common.bytes")}`;
  if (sizeBytes < 1048576) return `${n.format(Number((sizeBytes / 1024).toFixed(decimalPlaces)))} ${t("common.kilobyte")}`;
  if (sizeBytes < 1073741824)
    return `${n.format(Number((sizeBytes / 1048576).toFixed(decimalPlaces)))} ${t("common.megabyte")}`;
  return `${n.format(Number((sizeBytes / 1073741824).toFixed(decimalPlaces)))} ${t("common.gigabyte")}`;
}

/** Bilingual "time remaining until expiry" label from a raw unix timestamp. */
export function formatExpiry(expirationTimestamp: number | null | undefined): { remaining: string; date: string } {
  const t = i18n.t.bind(i18n);
  if (!expirationTimestamp) {
    return { remaining: t("common.unknown"), date: t("common.unknown") };
  }

  const expiryDate = new Date(expirationTimestamp * 1000);
  const dateFormatter = new Intl.DateTimeFormat(isFa() ? "fa-IR-u-ca-persian" : "en-US", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  const date = dateFormatter.format(expiryDate);

  const diffMs = expiryDate.getTime() - Date.now();
  if (diffMs <= 0) {
    return { remaining: t("common.expired"), date };
  }

  const totalSeconds = Math.floor(diffMs / 1000);
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);

  const parts: string[] = [];
  if (days) parts.push(`${numberFormatter().format(days)} ${t(days === 1 ? "common.day" : "common.days")}`);
  if (hours) parts.push(`${numberFormatter().format(hours)} ${t(hours === 1 ? "common.hour" : "common.hours")}`);
  if (minutes) parts.push(`${numberFormatter().format(minutes)} ${t(minutes === 1 ? "common.minute" : "common.minutes")}`);

  const remaining = parts.length ? `${parts.join(` ${t("common.and")} `)} ${t("common.remainingSuffix")}` : t("common.lessThanMinute");
  return { remaining, date };
}

/** Bilingual relative time label ("2 hours ago") from a raw unix timestamp. */
export function formatRelativeTime(timestamp: number | null | undefined): string {
  const t = i18n.t.bind(i18n);
  if (!timestamp) return t("common.unknown");

  const diffSeconds = Math.floor(Date.now() / 1000 - timestamp);
  if (diffSeconds < 60) return t("common.justNow");

  const minutes = Math.floor(diffSeconds / 60);
  if (minutes < 60) return t("common.minutesAgo", { count: minutes });

  const hours = Math.floor(diffSeconds / 3600);
  if (hours < 24) return t("common.hoursAgo", { count: hours });

  const days = Math.floor(diffSeconds / 86400);
  if (days < 30) return t("common.daysAgo", { count: days });

  return formatUnixDate(timestamp);
}

/** Bilingual relative label ("Today"/"Yesterday"/"3 days ago"/date) for an ISO date string. */
export function formatDayLabel(isoDate: string): string {
  const t = i18n.t.bind(i18n);
  const day = new Date(`${isoDate}T00:00:00`);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diffDays = Math.round((today.getTime() - day.getTime()) / 86400000);

  if (diffDays === 0) return t("common.today");
  if (diffDays === 1) return t("common.yesterday");
  if (diffDays >= 2 && diffDays <= 6) return t("common.daysAgo", { count: diffDays });

  const formatter = new Intl.DateTimeFormat(isFa() ? "fa-IR-u-ca-persian" : "en-US", {
    month: "2-digit",
    day: "2-digit",
  });
  return formatter.format(day);
}

/** Bilingual device/IP limit label from the raw limit count (0 = unlimited). */
export function formatIpLimit(ipLimit: number | null | undefined): string {
  const t = i18n.t.bind(i18n);
  if (!ipLimit) return t("common.noLimit");
  return t("common.usersCount", { count: ipLimit });
}

export function clampPercent(used: number, total: number): number {
  if (!total || total <= 0) return 0;
  return Math.min(100, Math.max(0, Math.round((used / total) * 100)));
}

export function copyToClipboard(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(text);
  return new Promise((resolve, reject) => {
    try {
      const el = document.createElement("textarea");
      el.value = text;
      el.style.position = "fixed";
      el.style.opacity = "0";
      document.body.appendChild(el);
      el.focus();
      el.select();
      document.execCommand("copy");
      document.body.removeChild(el);
      resolve();
    } catch (err) {
      reject(err instanceof Error ? err : new Error("copy failed"));
    }
  });
}
