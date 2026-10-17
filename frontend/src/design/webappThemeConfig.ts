/**
 * The admin-chosen web app colors, fetched from the public `/api/webapp/theme`
 * endpoint (no login: the login page is themed too). The last answer is kept
 * in localStorage so the next launch paints the right colors before the
 * request returns.
 */
import { coerceTheme, presetTheme } from "./webappThemes";
import type { WebappTheme } from "./webappThemes";

export interface ThemeChoice {
  id: string;
  name: string;
  theme: WebappTheme;
}

export interface WebappThemeConfig {
  mode: "telegram" | "custom";
  active: string;
  theme: WebappTheme | null;
  user_scheme: boolean;
  user_pick: boolean;
  version: number;
  choices: ThemeChoice[];
}

/** A user's own pick: "" follows the admin, "telegram" uses Telegram's colors, otherwise a theme id. */
export const PICK_ADMIN = "";
export const PICK_TELEGRAM = "telegram";

const CONFIG_URL = `${(import.meta.env.VITE_API_BASE as string | undefined) || "/api/webapp"}/theme`;
const CONFIG_STORAGE_KEY = "webapp_theme_config";
const PICK_STORAGE_KEY = "webapp_theme_pick";

export const FALLBACK_CONFIG: WebappThemeConfig = {
  mode: "telegram",
  active: "default",
  theme: null,
  user_scheme: true,
  user_pick: false,
  version: 0,
  choices: [],
};

function normalize(raw: unknown): WebappThemeConfig | null {
  if (!raw || typeof raw !== "object") return null;
  const data = raw as Partial<Record<keyof WebappThemeConfig, unknown>>;
  const choices = Array.isArray(data.choices)
    ? data.choices.flatMap((item) => {
        const choice = item as Partial<ThemeChoice> | null;
        const coerced = coerceTheme(choice?.theme);
        if (!choice || typeof choice.id !== "string" || !coerced) return [];
        return [{ id: choice.id, name: String(choice.name ?? ""), theme: coerced.theme }];
      })
    : [];
  return {
    mode: data.mode === "custom" ? "custom" : "telegram",
    active: typeof data.active === "string" && data.active ? data.active : "default",
    theme: coerceTheme(data.theme)?.theme ?? null,
    user_scheme: data.user_scheme !== false,
    user_pick: data.user_pick === true,
    version: Number(data.version) || 0,
    choices,
  };
}

export function readCachedConfig(): WebappThemeConfig {
  try {
    const raw = localStorage.getItem(CONFIG_STORAGE_KEY);
    if (raw) return normalize(JSON.parse(raw)) ?? FALLBACK_CONFIG;
  } catch {
    // ignore
  }
  return FALLBACK_CONFIG;
}

export async function fetchThemeConfig(): Promise<WebappThemeConfig | null> {
  try {
    const res = await fetch(CONFIG_URL, { cache: "no-store" });
    if (!res.ok) return null;
    const config = normalize(await res.json());
    if (config) {
      try {
        localStorage.setItem(CONFIG_STORAGE_KEY, JSON.stringify(config));
      } catch {
        // ignore
      }
    }
    return config;
  } catch {
    return null;
  }
}

export function readStoredPick(): string {
  try {
    return localStorage.getItem(PICK_STORAGE_KEY) ?? PICK_ADMIN;
  } catch {
    return PICK_ADMIN;
  }
}

export function storePick(pick: string): void {
  try {
    if (pick) localStorage.setItem(PICK_STORAGE_KEY, pick);
    else localStorage.removeItem(PICK_STORAGE_KEY);
  } catch {
    // ignore
  }
}

/** The admin's active theme; a preset prefers the bundled palette so it matches what admins preview. */
export function activeTheme(config: WebappThemeConfig): WebappTheme | null {
  if (config.mode !== "custom") return null;
  return presetTheme(config.active) ?? config.theme;
}

/**
 * The theme this user should see, or null for Telegram's own colors.
 * A pick only counts while the admin still lets users pick.
 */
export function resolveTheme(config: WebappThemeConfig, pick: string): WebappTheme | null {
  if (config.user_pick && pick) {
    if (pick === PICK_TELEGRAM) return null;
    const picked = presetTheme(pick) ?? config.choices.find((choice) => choice.id === pick)?.theme;
    if (picked) return picked;
  }
  return activeTheme(config);
}
