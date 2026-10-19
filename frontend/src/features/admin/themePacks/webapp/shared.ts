import type { TFunction } from "i18next";
import { THEME_PRESETS, coerceTheme } from "../../../../design/webappThemes";
import type { Palette, PaletteKey, WebappTheme } from "../../../../design/webappThemes";
import { THEME_PACK_FORMAT } from "../../../../types/panel";
import type { WebappThemeEntry, WebappThemeSharePack } from "../../../../types/panel";
import { MAX_PACK_FILE_BYTES } from "../shared";

export const WEBAPP_THEMES_QUERY_KEY = ["webapp-themes"];
export const CUSTOM_PREFIX = "custom:";

export type LibraryKind = "preset" | "custom" | "imported";

/** One card in the library: a built-in preset or a theme from the admin's library. */
export interface LibraryTheme {
  /** The id the backend activates: a preset id or "custom:<id>". */
  key: string;
  name: string;
  theme: WebappTheme;
  kind: LibraryKind;
  entry?: WebappThemeEntry;
}

export const presetName = (t: TFunction, id: string) => t(`webappTheme.presets.${id}`, { defaultValue: id });

export function buildLibrary(t: TFunction, themes: WebappThemeEntry[]): LibraryTheme[] {
  const custom = themes.map<LibraryTheme>((entry) => ({
    key: `${CUSTOM_PREFIX}${entry.id}`,
    name: entry.name,
    theme: entry.theme,
    kind: entry.imported ? "imported" : "custom",
    entry,
  }));
  const presets = THEME_PRESETS.map<LibraryTheme>((preset) => ({
    key: preset.id,
    name: presetName(t, preset.id),
    theme: preset.theme,
    kind: "preset",
  }));
  return [...custom, ...presets];
}

/** Editor rows, grouped the way an admin thinks about a screen. */
export const COLOR_GROUPS: { key: string; colors: PaletteKey[] }[] = [
  { key: "backgrounds", colors: ["bg", "surface", "surface_2"] },
  { key: "text", colors: ["text", "text_muted"] },
  { key: "brand", colors: ["primary", "primary_strong", "primary_text", "accent"] },
  { key: "status", colors: ["success", "warning", "danger"] },
];

export interface ContrastCheck {
  fg: PaletteKey;
  bg: PaletteKey;
  min: number;
  label: string;
}

/** Pairs that must stay readable; 4.5 for body text, 3 for large or bold text and buttons. */
export const CONTRAST_CHECKS: ContrastCheck[] = [
  { fg: "text", bg: "bg", min: 4.5, label: "textOnBg" },
  { fg: "text", bg: "surface", min: 4.5, label: "textOnCard" },
  { fg: "text_muted", bg: "surface", min: 3, label: "mutedOnCard" },
  { fg: "primary_text", bg: "primary", min: 3, label: "buttonText" },
  { fg: "accent", bg: "surface", min: 3, label: "linkOnCard" },
];

export function cloneTheme(theme: WebappTheme): WebappTheme {
  return { radius: theme.radius, light: { ...theme.light }, dark: { ...theme.dark } };
}

export function swatches(palette: Palette): string[] {
  return [palette.primary, palette.accent, palette.bg];
}

/** Share file for a theme: a theme pack that carries only the web app section. */
export function sharePack(name: string, theme: WebappTheme, bot?: string): WebappThemeSharePack {
  return {
    format: THEME_PACK_FORMAT,
    version: 1,
    name,
    source: { bot, created_at: Math.floor(Date.now() / 1000) },
    webapp: theme,
  };
}

export interface ParsedShare {
  name: string;
  sourceBot: string;
  theme: WebappTheme;
  /** Colors missing from the file, filled in from the default theme. */
  filled: number;
}

/** Reads a shared theme from a file or pasted code; throws an Error whose message is an i18n key. */
export function parseShareText(text: string): ParsedShare {
  if (new Blob([text]).size > MAX_PACK_FILE_BYTES) throw new Error("panel.themePacks.errorTooLarge");
  let data: unknown;
  try {
    data = JSON.parse(text.replace(/^﻿/, ""));
  } catch {
    throw new Error("panel.themePacks.errorNotJson");
  }
  const pack = data as Partial<WebappThemeSharePack> & { texts?: unknown; buttons?: unknown; layout?: unknown };
  if (!pack || typeof pack !== "object" || pack.format !== THEME_PACK_FORMAT) {
    throw new Error("panel.themePacks.errorNotPack");
  }
  if (!pack.webapp) {
    throw new Error(
      pack.texts || pack.buttons || pack.layout ? "panel.webappThemes.errorTextPack" : "panel.webappThemes.errorNoColors"
    );
  }
  const coerced = coerceTheme(pack.webapp);
  if (!coerced) throw new Error("panel.webappThemes.errorNoColors");
  return {
    name: typeof pack.name === "string" ? pack.name.slice(0, 100) : "",
    sourceBot: typeof pack.source?.bot === "string" ? pack.source.bot.slice(0, 40) : "",
    theme: coerced.theme,
    filled: coerced.filled,
  };
}
