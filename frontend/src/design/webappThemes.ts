/**
 * Web app color themes: the palette shape shared with the backend
 * (app/services/webapp_theme.py), color math, the built-in presets, and the
 * CSS variables a theme turns into. A theme maps onto the same tokens as
 * design/theme.css, so every component picks it up without changes.
 */
import type { CSSProperties } from "react";

export const PALETTE_KEYS = [
  "bg",
  "surface",
  "surface_2",
  "text",
  "text_muted",
  "primary",
  "primary_strong",
  "primary_text",
  "accent",
  "success",
  "warning",
  "danger",
] as const;

export type PaletteKey = (typeof PALETTE_KEYS)[number];
export type Scheme = "light" | "dark";
export type Palette = Record<PaletteKey, string> & { border_alpha: number };

export interface WebappTheme {
  radius: number;
  light: Palette;
  dark: Palette;
}

export interface ThemePreset {
  id: string;
  theme: WebappTheme;
}

export const MIN_RADIUS = 4;
export const MAX_RADIUS = 26;
export const MAX_BORDER_ALPHA = 0.35;
export const DEFAULT_PRESET_ID = "default";

/* ---------------- color math ---------------- */

const clamp = (n: number, min: number, max: number) => Math.min(max, Math.max(min, n));

export function isHex(value: unknown): value is string {
  return typeof value === "string" && /^#[0-9a-f]{6}$/i.test(value.trim());
}

export function hexToRgb(hex: string): [number, number, number] {
  const match = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex.trim());
  if (!match) return [0, 0, 0];
  return [parseInt(match[1] ?? "0", 16), parseInt(match[2] ?? "0", 16), parseInt(match[3] ?? "0", 16)];
}

export function hslToHex(h: number, s: number, l: number): string {
  const hue = ((h % 360) + 360) % 360;
  const sat = clamp(s, 0, 100) / 100;
  const light = clamp(l, 0, 100) / 100;
  const k = (n: number) => (n + hue / 30) % 12;
  const a = sat * Math.min(light, 1 - light);
  const f = (n: number) => light - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
  return `#${[f(0), f(8), f(4)].map((x) => Math.round(x * 255).toString(16).padStart(2, "0")).join("")}`;
}

export function hexToHsl(hex: string): [number, number, number] {
  const [r, g, b] = hexToRgb(hex).map((x) => x / 255) as [number, number, number];
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;
  const d = max - min;
  let h = 0;
  let s = 0;
  if (d) {
    s = d / (1 - Math.abs(2 * l - 1));
    if (max === r) h = ((g - b) / d) % 6;
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h *= 60;
  }
  return [(h + 360) % 360, s * 100, l * 100];
}

function luminance(hex: string): number {
  const weights = [0.2126, 0.7152, 0.0722];
  return hexToRgb(hex).reduce((sum, channel, i) => {
    const c = channel / 255;
    return sum + (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4) * (weights[i] ?? 0);
  }, 0);
}

/** WCAG contrast ratio between two colors (1 to 21). */
export function contrast(a: string, b: string): number {
  const x = luminance(a);
  const y = luminance(b);
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}

/** White or near-black, whichever reads on top of ``bg``. */
export function onColor(bg: string): string {
  return contrast("#ffffff", bg) >= 3.2 ? "#ffffff" : "#0b0d14";
}

/** Moves ``fg``'s lightness away from ``bg`` until the pair reaches ``min`` contrast. */
export function fixContrast(fg: string, bg: string, min: number): string {
  const [h, s, start] = hexToHsl(fg);
  const step = luminance(bg) > 0.4 ? -1.5 : 1.5;
  let l = start;
  for (let i = 0; i < 70 && contrast(hslToHex(h, s, l), bg) < min; i += 1) l = clamp(l + step, 0, 100);
  return hslToHex(h, s, l);
}

/* ---------------- generator ---------------- */

export interface GenerateOptions {
  /** Hue of the brand color. */
  hue: number;
  sat?: number;
  /** Hue the backgrounds and text are tinted with; defaults to ``hue``. */
  neutralHue?: number;
  accentHue?: number;
  accentSat?: number;
  /** Saturation of the light backgrounds / dark backgrounds. */
  tint?: number;
  darkTint?: number;
  /** Lightness of the light page background / dark page background. */
  bgL?: number;
  darkBgL?: number;
  primaryL?: number;
  darkPrimaryL?: number;
  radius?: number;
}

/** One brand hue in, a complete light + dark theme out (also used by the editor's quick start). */
export function generateTheme(options: GenerateOptions): WebappTheme {
  const {
    hue,
    sat = 80,
    neutralHue = hue,
    accentHue = hue + 32,
    accentSat = sat * 0.9,
    tint = 28,
    darkTint = 30,
    bgL = 96.5,
    darkBgL = 6,
    primaryL = 50,
    darkPrimaryL = 62,
    radius = 16,
  } = options;
  const nh = neutralHue;

  const lightSurface = hslToHex(nh, tint, Math.min(100, bgL + 3.5));
  const light: Palette = {
    bg: hslToHex(nh, tint, bgL),
    surface: lightSurface,
    surface_2: hslToHex(nh, tint * 0.85, bgL - 3),
    text: hslToHex(nh, 30, 9),
    text_muted: fixContrast(hslToHex(nh, 10, 45), lightSurface, 4.2),
    primary: hslToHex(hue, sat, primaryL),
    primary_strong: hslToHex(hue, sat, primaryL - 9),
    primary_text: "#ffffff",
    accent: fixContrast(hslToHex(accentHue, accentSat, 40), lightSurface, 3.2),
    success: "#16a34a",
    warning: "#d97706",
    danger: "#dc2626",
    border_alpha: 0.11,
  };
  light.primary_text = onColor(light.primary);

  const darkSurface = hslToHex(nh, darkTint * 0.87, darkBgL + 4.5);
  const dark: Palette = {
    bg: hslToHex(nh, darkTint, darkBgL),
    surface: darkSurface,
    surface_2: hslToHex(nh, darkTint * 0.73, darkBgL + 9),
    text: hslToHex(nh, 20, 95),
    text_muted: fixContrast(hslToHex(nh, 12, 62), darkSurface, 4.2),
    primary: hslToHex(hue, sat, darkPrimaryL),
    primary_strong: hslToHex(hue, sat, darkPrimaryL + 12),
    primary_text: "#ffffff",
    accent: fixContrast(hslToHex(accentHue, accentSat * 0.95, 66), darkSurface, 3.2),
    success: "#4ade80",
    warning: "#fbbf24",
    danger: "#f87171",
    border_alpha: 0.12,
  };
  dark.primary_text = onColor(dark.primary);

  return { radius: clamp(Math.round(radius), MIN_RADIUS, MAX_RADIUS), light, dark };
}

function withOverrides(theme: WebappTheme, light: Partial<Palette>, dark: Partial<Palette>): WebappTheme {
  return { radius: theme.radius, light: { ...theme.light, ...light }, dark: { ...theme.dark, ...dark } };
}

/* ---------------- presets ---------------- */

/** The stock look, identical to the fallback palettes in design/theme.css. */
export const DEFAULT_THEME: WebappTheme = {
  radius: 16,
  light: {
    bg: "#f4f5f9",
    surface: "#ffffff",
    surface_2: "#eef0f6",
    text: "#10131c",
    text_muted: "#6b7280",
    primary: "#3b82f6",
    primary_strong: "#2563eb",
    primary_text: "#ffffff",
    accent: "#06b6d4",
    success: "#16a34a",
    warning: "#d97706",
    danger: "#dc2626",
    border_alpha: 0.11,
  },
  dark: {
    bg: "#0a0c14",
    surface: "#131522",
    surface_2: "#1b1e2f",
    text: "#f1f2f7",
    text_muted: "#8b8fa3",
    primary: "#60a5fa",
    primary_strong: "#93c5fd",
    primary_text: "#ffffff",
    accent: "#22d3ee",
    success: "#4ade80",
    warning: "#fbbf24",
    danger: "#f87171",
    border_alpha: 0.12,
  },
};

const gen = generateTheme;

/** Built-in presets, in the order the library shows them. Names live in locales (webappTheme.presets.<id>). */
export const THEME_PRESETS: ThemePreset[] = [
  { id: "default", theme: DEFAULT_THEME },
  {
    id: "telegram",
    theme: withOverrides(
      gen({ hue: 207, sat: 70, tint: 0, darkTint: 28, darkBgL: 13, radius: 14 }),
      { bg: "#ffffff", surface: "#ffffff", surface_2: "#f1f1f4", text: "#000000", text_muted: "#707579", primary: "#2481cc", primary_strong: "#1c6fb0", accent: "#2481cc" },
      { bg: "#17212b", surface: "#232e3c", surface_2: "#2b3949", text: "#f5f5f5", text_muted: "#93a3b5", primary: "#5eb5f7", primary_strong: "#8ccbfa", accent: "#6ab3f3" }
    ),
  },
  { id: "ocean", theme: gen({ hue: 205, sat: 85, radius: 18 }) },
  { id: "sky", theme: gen({ hue: 196, sat: 90, tint: 45, radius: 22 }) },
  { id: "teal", theme: gen({ hue: 184, sat: 72, radius: 14 }) },
  { id: "emerald", theme: gen({ hue: 158, sat: 70 }) },
  { id: "mint", theme: gen({ hue: 165, sat: 55, tint: 40, accentHue: 200, radius: 22 }) },
  { id: "forest", theme: gen({ hue: 140, sat: 45, accentHue: 38, accentSat: 80, darkTint: 22, radius: 12 }) },
  { id: "lime", theme: gen({ hue: 84, sat: 72, primaryL: 42, darkPrimaryL: 58, accentHue: 160, radius: 16 }) },
  { id: "amber", theme: gen({ hue: 38, sat: 92, primaryL: 47, accentHue: 18, radius: 16 }) },
  { id: "sunset", theme: gen({ hue: 22, sat: 88, accentHue: 340, radius: 20 }) },
  { id: "peach", theme: gen({ hue: 18, sat: 90, tint: 70, bgL: 97, primaryL: 58, accentHue: 350, radius: 24 }) },
  { id: "coral", theme: gen({ hue: 8, sat: 80, accentHue: 190, radius: 18 }) },
  { id: "crimson", theme: gen({ hue: 352, sat: 75, primaryL: 46, accentHue: 30, radius: 12 }) },
  { id: "ruby", theme: gen({ hue: 345, sat: 60, primaryL: 40, darkPrimaryL: 60, darkTint: 38, darkBgL: 7, accentHue: 40, radius: 14 }) },
  { id: "rose", theme: gen({ hue: 342, sat: 76, radius: 22 }) },
  { id: "sakura", theme: gen({ hue: 330, sat: 62, tint: 60, bgL: 97, primaryL: 58, accentHue: 280, radius: 24 }) },
  { id: "violet", theme: gen({ hue: 262, sat: 78, radius: 18 }) },
  { id: "lavender", theme: gen({ hue: 250, sat: 55, tint: 45, primaryL: 60, accentHue: 300, radius: 22 }) },
  { id: "royal", theme: gen({ hue: 235, sat: 70, primaryL: 45, accentHue: 42, accentSat: 85, darkTint: 40, radius: 14 }) },
  { id: "aurora", theme: gen({ hue: 168, sat: 75, neutralHue: 230, accentHue: 280, accentSat: 70, darkTint: 35, radius: 20 }) },
  {
    id: "midnight_gold",
    theme: gen({ hue: 42, sat: 88, neutralHue: 225, primaryL: 44, darkPrimaryL: 60, tint: 20, darkTint: 45, darkBgL: 7, accentHue: 205, radius: 12 }),
  },
  { id: "coffee", theme: gen({ hue: 28, sat: 45, tint: 30, primaryL: 38, darkPrimaryL: 60, darkTint: 18, accentHue: 160, accentSat: 45, radius: 14 }) },
  {
    id: "paper",
    theme: withOverrides(
      gen({ hue: 32, sat: 55, tint: 40, bgL: 95, primaryL: 40, darkTint: 14, darkBgL: 9, radius: 10 }),
      { bg: "#f5efe3", surface: "#fbf7ef", surface_2: "#ece4d3", text: "#2b2117", text_muted: "#6f6150" },
      { bg: "#1c1915", surface: "#25211b", surface_2: "#2f2a22", text: "#ece3d3", text_muted: "#a89a86" }
    ),
  },
  { id: "slate", theme: gen({ hue: 215, sat: 28, tint: 18, darkTint: 18, primaryL: 42, darkPrimaryL: 66, accentHue: 190, accentSat: 60, radius: 10 }) },
  {
    id: "graphite",
    theme: withOverrides(
      gen({ hue: 230, sat: 6, tint: 8, darkTint: 6, radius: 10 }),
      { primary: "#1f2430", primary_strong: "#0f1219", primary_text: "#ffffff", accent: "#4b5bd6" },
      { primary: "#e6e8ee", primary_strong: "#ffffff", primary_text: "#0b0d14", accent: "#8b9cff" }
    ),
  },
  {
    id: "amoled",
    theme: withOverrides(
      gen({ hue: 217, sat: 90, radius: 16 }),
      {},
      { bg: "#000000", surface: "#0b0b0d", surface_2: "#16161a", text: "#f4f4f6", text_muted: "#8e8e98", border_alpha: 0.14 }
    ),
  },
  {
    id: "cyber",
    theme: withOverrides(
      gen({ hue: 300, sat: 85, neutralHue: 250, accentHue: 182, accentSat: 90, darkTint: 50, darkBgL: 6, radius: 6 }),
      {},
      { primary: "#e94cf5", primary_strong: "#f59cfb", accent: "#2ff3e0" }
    ),
  },
  {
    id: "nord",
    theme: withOverrides(
      gen({ hue: 210, sat: 35, radius: 12 }),
      { bg: "#eceff4", surface: "#ffffff", surface_2: "#e5e9f0", text: "#2e3440", text_muted: "#5c6779", primary: "#5e81ac", primary_strong: "#4c6a91", primary_text: "#ffffff", accent: "#4c8a9c", success: "#5f8f4e", warning: "#b5862a", danger: "#bf616a" },
      { bg: "#2e3440", surface: "#3b4252", surface_2: "#434c5e", text: "#eceff4", text_muted: "#a5afc2", primary: "#88c0d0", primary_strong: "#8fbcbb", primary_text: "#2e3440", accent: "#81a1c1", success: "#a3be8c", warning: "#ebcb8b", danger: "#bf616a" }
    ),
  },
  {
    id: "dracula",
    theme: withOverrides(
      gen({ hue: 265, sat: 85, radius: 14 }),
      { bg: "#f8f8f2", surface: "#ffffff", surface_2: "#ecebe4", text: "#282a36", text_muted: "#5f6380", primary: "#7c4dff", primary_strong: "#6236e0", primary_text: "#ffffff", accent: "#c2338a", success: "#1f9d55", warning: "#b7791f", danger: "#d63a3a" },
      { bg: "#21222c", surface: "#282a36", surface_2: "#343746", text: "#f8f8f2", text_muted: "#a2a6c4", primary: "#bd93f9", primary_strong: "#d6bcfc", primary_text: "#21222c", accent: "#ff79c6", success: "#50fa7b", warning: "#f1fa8c", danger: "#ff5555" }
    ),
  },
  {
    id: "solarized",
    theme: withOverrides(
      gen({ hue: 205, sat: 70, radius: 10 }),
      { bg: "#fdf6e3", surface: "#fffbf0", surface_2: "#eee8d5", text: "#073642", text_muted: "#586e75", primary: "#268bd2", primary_strong: "#1a6fab", primary_text: "#ffffff", accent: "#2aa198", success: "#859900", warning: "#b58900", danger: "#dc322f" },
      { bg: "#002b36", surface: "#073642", surface_2: "#0d4250", text: "#eee8d5", text_muted: "#93a1a1", primary: "#268bd2", primary_strong: "#5aa9e0", primary_text: "#ffffff", accent: "#2aa198", success: "#859900", warning: "#b58900", danger: "#dc322f" }
    ),
  },
  {
    id: "github",
    theme: withOverrides(
      gen({ hue: 212, sat: 90, radius: 8 }),
      { bg: "#f6f8fa", surface: "#ffffff", surface_2: "#eaeef2", text: "#1f2328", text_muted: "#59636e", primary: "#0969da", primary_strong: "#0550ae", primary_text: "#ffffff", accent: "#8250df", success: "#1a7f37", warning: "#9a6700", danger: "#cf222e" },
      { bg: "#0d1117", surface: "#151b23", surface_2: "#212830", text: "#f0f6fc", text_muted: "#9198a1", primary: "#4493f8", primary_strong: "#79b8ff", primary_text: "#ffffff", accent: "#ab7df8", success: "#3fb950", warning: "#d29922", danger: "#f85149" }
    ),
  },
];

const PRESETS_BY_ID = new Map(THEME_PRESETS.map((preset) => [preset.id, preset.theme]));

export function presetTheme(id: string): WebappTheme | undefined {
  return PRESETS_BY_ID.get(id);
}

/** Built-in presets a user may pick from, offered alongside the admin's custom themes. */
export const USER_PICKABLE_PRESETS = THEME_PRESETS.map((preset) => preset.id);

/* ---------------- validation ---------------- */

/** Fills gaps from the default theme; returns null when the data is not a theme at all. */
export function coerceTheme(raw: unknown): { theme: WebappTheme; filled: number } | null {
  if (!raw || typeof raw !== "object") return null;
  const data = raw as Partial<Record<Scheme, Record<string, unknown>>> & { radius?: unknown };
  if (!data.light && !data.dark) return null;
  let filled = 0;
  const palette = (scheme: Scheme): Palette => {
    const source = (data[scheme] ?? {}) as Record<string, unknown>;
    const fallback = DEFAULT_THEME[scheme];
    const out = { ...fallback };
    for (const key of PALETTE_KEYS) {
      const value = source[key];
      if (isHex(value)) out[key] = value.trim().toLowerCase();
      else filled += 1;
    }
    const alpha = Number(source.border_alpha);
    out.border_alpha = Number.isFinite(alpha) ? clamp(alpha, 0, MAX_BORDER_ALPHA) : fallback.border_alpha;
    return out;
  };
  const radius = Number(data.radius);
  return {
    theme: {
      radius: Number.isFinite(radius) ? clamp(Math.round(radius), MIN_RADIUS, MAX_RADIUS) : DEFAULT_THEME.radius,
      light: palette("light"),
      dark: palette("dark"),
    },
    filled,
  };
}

/* ---------------- CSS variables ---------------- */

const triplet = (hex: string) => hexToRgb(hex).join(" ");

const RADIUS_SCALE: Record<string, number> = {
  "--radius-xs": 0.625,
  "--radius-sm": 0.75,
  "--radius-md": 1,
  "--radius-lg": 1.5,
  "--radius-xl": 1.75,
  "--radius-2xl": 2,
  "--radius-3xl": 2.5,
};

/** Every CSS variable a theme sets; ThemeProvider clears exactly these when a theme is removed. */
export const THEME_VARIABLES = [
  "--c-bg-rgb",
  "--c-surface-rgb",
  "--c-surface-2-rgb",
  "--c-text-rgb",
  "--c-text-muted-rgb",
  "--c-primary-rgb",
  "--c-primary-strong-rgb",
  "--c-primary-text-rgb",
  "--c-accent-rgb",
  "--c-success-rgb",
  "--c-warning-rgb",
  "--c-danger-rgb",
  "--c-border-rgb",
  "--c-border-alpha",
  "--shadow-sm",
  "--shadow-md",
  "--shadow-lg",
  ...Object.keys(RADIUS_SCALE),
];

/** The design tokens for one scheme of a theme, keyed by CSS variable name. */
export function themeVariables(theme: WebappTheme, scheme: Scheme): Record<string, string> {
  const p = theme[scheme];
  const primary = triplet(p.primary);
  const vars: Record<string, string> = {
    "--c-bg-rgb": triplet(p.bg),
    "--c-surface-rgb": triplet(p.surface),
    "--c-surface-2-rgb": triplet(p.surface_2),
    "--c-text-rgb": triplet(p.text),
    "--c-text-muted-rgb": triplet(p.text_muted),
    "--c-primary-rgb": primary,
    "--c-primary-strong-rgb": triplet(p.primary_strong),
    "--c-primary-text-rgb": triplet(p.primary_text),
    "--c-accent-rgb": triplet(p.accent),
    "--c-success-rgb": triplet(p.success),
    "--c-warning-rgb": triplet(p.warning),
    "--c-danger-rgb": triplet(p.danger),
    "--c-border-rgb": triplet(p.text),
    "--c-border-alpha": String(p.border_alpha),
  };
  if (scheme === "dark") {
    vars["--shadow-sm"] = "inset 0 1px 0 rgb(255 255 255 / 0.05), 0 3px 10px rgb(0 0 0 / 0.35)";
    vars["--shadow-md"] = "inset 0 1px 0 rgb(255 255 255 / 0.06), 0 16px 36px -10px rgb(0 0 0 / 0.55)";
    vars["--shadow-lg"] = "inset 0 1px 0 rgb(255 255 255 / 0.07), 0 28px 58px -14px rgb(0 0 0 / 0.65)";
  } else {
    const ink = triplet(p.text);
    vars["--shadow-sm"] = `0 1px 2px rgb(${ink} / 0.04), 0 4px 12px -4px rgb(${ink} / 0.10)`;
    vars["--shadow-md"] = `0 4px 10px -4px rgb(${ink} / 0.10), 0 14px 32px -10px rgb(${primary} / 0.22)`;
    vars["--shadow-lg"] = `0 8px 20px -6px rgb(${ink} / 0.14), 0 26px 52px -14px rgb(${primary} / 0.30)`;
  }
  for (const [name, factor] of Object.entries(RADIUS_SCALE)) {
    vars[name] = `${Math.round(theme.radius * factor)}px`;
  }
  return vars;
}

/** Inline style that scopes a theme to one element (used by previews). */
export function themeStyle(theme: WebappTheme, scheme: Scheme): CSSProperties {
  return themeVariables(theme, scheme) as CSSProperties;
}
