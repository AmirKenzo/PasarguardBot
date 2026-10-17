import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  FALLBACK_CONFIG,
  fetchThemeConfig,
  readCachedConfig,
  readStoredPick,
  resolveTheme,
  storePick,
} from "./webappThemeConfig";
import type { WebappThemeConfig } from "./webappThemeConfig";
import { THEME_VARIABLES, themeVariables } from "./webappThemes";
import type { WebappTheme } from "./webappThemes";

type Scheme = "light" | "dark";
export type ThemeMode = "auto" | "light" | "dark";

interface ThemeContextValue {
  scheme: Scheme;
  mode: ThemeMode;
  setMode: (mode: ThemeMode) => void;
  config: WebappThemeConfig;
  canChangeScheme: boolean;
  pick: string;
  setPick: (pick: string) => void;
  reloadConfig: () => Promise<void>;
}

const ThemeContext = createContext<ThemeContextValue>({
  scheme: "dark",
  mode: "auto",
  setMode: () => {},
  config: FALLBACK_CONFIG,
  canChangeScheme: true,
  pick: "",
  setPick: () => {},
  reloadConfig: async () => {},
});

const MODE_STORAGE_KEY = "webapp_theme_mode";

function hexToRgbTriplet(hex: string): string | null {
  const match = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex.trim());
  if (!match) return null;
  const [, r = "00", g = "00", b = "00"] = match;
  return `${parseInt(r, 16)} ${parseInt(g, 16)} ${parseInt(b, 16)}`;
}

function setVar(root: CSSStyleDeclaration, name: string, hex: string | undefined) {
  if (!hex) return;
  const rgb = hexToRgbTriplet(hex);
  if (rgb) root.setProperty(name, rgb);
}

function clearInlineOverrides() {
  const root = document.documentElement.style;
  for (const name of THEME_VARIABLES) root.removeProperty(name);
}

/** Maps Telegram theme param colors onto our CSS token names when available. */
function applyTelegramColors(): boolean {
  const webApp = window.Telegram?.WebApp;
  const t = webApp?.themeParams;
  if (!webApp || !t || !t.bg_color) return false;

  const root = document.documentElement.style;
  setVar(root, "--c-bg-rgb", t.bg_color);
  setVar(root, "--c-surface-rgb", t.section_bg_color || t.secondary_bg_color);
  setVar(root, "--c-surface-2-rgb", t.secondary_bg_color);
  setVar(root, "--c-text-rgb", t.text_color);
  setVar(root, "--c-text-muted-rgb", t.hint_color);
  setVar(root, "--c-primary-rgb", t.button_color);
  setVar(root, "--c-primary-strong-rgb", t.button_color);
  setVar(root, "--c-primary-text-rgb", t.button_text_color);
  setVar(root, "--c-accent-rgb", t.link_color);
  setVar(root, "--c-danger-rgb", t.destructive_text_color);
  return true;
}

let telegramChromeTinted = false;

/** Hands Telegram's header and background back to its own theme after a custom theme was removed. */
function resetTelegramChrome() {
  if (!telegramChromeTinted) return;
  telegramChromeTinted = false;
  try {
    window.Telegram?.WebApp?.setHeaderColor?.("bg_color");
    window.Telegram?.WebApp?.setBackgroundColor?.("bg_color");
  } catch {
    // ignore
  }
}

/** Paints an admin theme over the CSS fallbacks, and Telegram's own header/background to match. */
function applyCustomTheme(theme: WebappTheme, scheme: Scheme) {
  clearInlineOverrides();
  const root = document.documentElement.style;
  for (const [name, value] of Object.entries(themeVariables(theme, scheme))) root.setProperty(name, value);
  const webApp = window.Telegram?.WebApp;
  try {
    webApp?.setHeaderColor?.(theme[scheme].surface);
    webApp?.setBackgroundColor?.(theme[scheme].bg);
    telegramChromeTinted = Boolean(webApp);
  } catch {
    // Older Telegram clients reject custom colors; the page itself is still themed.
  }
}

function detectSystemScheme(): Scheme {
  const webApp = window.Telegram?.WebApp;
  if (webApp?.colorScheme) return webApp.colorScheme;
  if (typeof window.matchMedia === "function" && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    return "dark";
  }
  return "light";
}

function readStoredMode(): ThemeMode {
  try {
    const stored = localStorage.getItem(MODE_STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "auto") return stored;
  } catch {
    // ignore
  }
  return "auto";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [storedMode, setModeState] = useState<ThemeMode>(() =>
    typeof window === "undefined" ? "auto" : readStoredMode()
  );
  const [config, setConfig] = useState<WebappThemeConfig>(() =>
    typeof window === "undefined" ? FALLBACK_CONFIG : readCachedConfig()
  );
  const [pick, setPickState] = useState<string>(() => (typeof window === "undefined" ? "" : readStoredPick()));
  // A locked switch always follows the device / Telegram, whatever the user chose before.
  const mode: ThemeMode = config.user_scheme ? storedMode : "auto";
  const [scheme, setScheme] = useState<Scheme>(() =>
    typeof window === "undefined" ? "dark" : mode === "auto" ? detectSystemScheme() : mode
  );
  const theme = useMemo(() => resolveTheme(config, pick), [config, pick]);

  const setMode = useCallback((next: ThemeMode) => {
    setModeState(next);
    try {
      localStorage.setItem(MODE_STORAGE_KEY, next);
    } catch {
      // ignore
    }
  }, []);

  const setPick = useCallback((next: string) => {
    setPickState(next);
    storePick(next);
  }, []);

  const reloadConfig = useCallback(async () => {
    const fresh = await fetchThemeConfig();
    if (fresh) setConfig(fresh);
  }, []);

  useEffect(() => {
    void reloadConfig();
  }, [reloadConfig]);

  useEffect(() => {
    const webApp = window.Telegram?.WebApp;

    const paint = (next: Scheme) => {
      setScheme(next);
      document.documentElement.setAttribute("data-theme", next);
      if (theme) {
        applyCustomTheme(theme, next);
        return;
      }
      clearInlineOverrides();
      resetTelegramChrome();
      if (mode === "auto") applyTelegramColors();
    };

    if (mode === "auto") {
      const applyAuto = () => paint(detectSystemScheme());
      applyAuto();
      if (webApp) {
        webApp.onEvent("themeChanged", applyAuto);
        return () => webApp.offEvent("themeChanged", applyAuto);
      }
      const media = window.matchMedia("(prefers-color-scheme: dark)");
      media.addEventListener("change", applyAuto);
      return () => media.removeEventListener("change", applyAuto);
    }

    paint(mode);
    return undefined;
  }, [mode, theme]);

  const value = useMemo<ThemeContextValue>(
    () => ({
      scheme,
      mode,
      setMode,
      config,
      canChangeScheme: config.user_scheme,
      pick,
      setPick,
      reloadConfig,
    }),
    [scheme, mode, setMode, config, pick, setPick, reloadConfig]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  return useContext(ThemeContext);
}
