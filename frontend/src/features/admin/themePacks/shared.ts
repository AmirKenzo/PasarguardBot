import type { TFunction } from "i18next";
import { THEME_PACK_FORMAT } from "../../../types/panel";
import type { ThemePackCounts, ThemePackData, ThemePackItem } from "../../../types/panel";

export const THEME_PACKS_QUERY_KEY = ["theme-packs"];
/** Applying or undoing a pack changes what the texts and keyboard pages show too. */
export const INVALIDATE_ALL = [THEME_PACKS_QUERY_KEY, ["texts"], ["keyboard"]];
export const MAX_PACK_FILE_BYTES = 1_000_000;
export const APPLICABLE_STATUSES = new Set(["new", "changed"]);

export function isApplicable(item: ThemePackItem): boolean {
  return APPLICABLE_STATUSES.has(item.status);
}

export const statusLabels = (t: TFunction): Record<string, string> => ({
  new: t("panel.themePacks.status.new"),
  changed: t("panel.themePacks.status.changed"),
  same: t("panel.themePacks.status.same"),
  invalid: t("panel.themePacks.status.invalid"),
  unknown: t("panel.themePacks.status.unknown"),
});

export const statusTone: Record<string, "primary" | "warning" | "muted" | "danger"> = {
  new: "primary",
  changed: "warning",
  same: "muted",
  invalid: "danger",
  unknown: "muted",
};

/** Item warnings, item errors and inventory hints share one label table. */
export const issueLabel = (t: TFunction, code: string): string =>
  t(`panel.themePacks.issues.${code}`, { defaultValue: code });

export const hintLabel = (t: TFunction, code: string): string => issueLabel(t, `sensitive_${code}`);

export function countsLabel(t: TFunction, counts: ThemePackCounts): string {
  const parts = [t("panel.themePacks.countTexts", { count: counts.texts ?? 0 })];
  parts.push(t("panel.themePacks.countButtons", { count: counts.buttons ?? 0 }));
  if (counts.layout) parts.push(t("panel.themePacks.countLayout"));
  return parts.join(" · ");
}

export function packCounts(pack: ThemePackData): ThemePackCounts {
  return {
    texts: Object.values(pack.texts ?? {}).reduce((sum, langs) => sum + Object.keys(langs).length, 0),
    buttons: Object.keys(pack.buttons ?? {}).length,
    layout: pack.layout ? 1 : 0,
  };
}

export function formatDate(seconds: number, locale: string): string {
  try {
    return new Date(seconds * 1000).toLocaleDateString(locale, { year: "numeric", month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

/** Reads a pack from file or pasted text; throws an Error whose message is an i18n key. */
export function parsePackText(text: string): ThemePackData {
  if (new Blob([text]).size > MAX_PACK_FILE_BYTES) throw new Error("panel.themePacks.errorTooLarge");
  let data: unknown;
  try {
    data = JSON.parse(text.replace(/^﻿/, ""));
  } catch {
    throw new Error("panel.themePacks.errorNotJson");
  }
  if (!data || typeof data !== "object" || (data as ThemePackData).format !== THEME_PACK_FORMAT) {
    throw new Error("panel.themePacks.errorNotPack");
  }
  return data as ThemePackData;
}

export function downloadPack(pack: ThemePackData, fileName: string): void {
  const blob = new Blob([JSON.stringify(pack, null, 2)], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
