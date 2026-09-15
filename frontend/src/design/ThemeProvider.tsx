import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

type Scheme = "light" | "dark";
export type ThemeMode = "auto" | "light" | "dark";

interface ThemeContextValue {
  scheme: Scheme;
  mode: ThemeMode;
  setMode: (mode: ThemeMode) => void;
}

const ThemeContext = createContext<ThemeContextValue>({ scheme: "dark", mode: "auto", setMode: () => {} });

const MODE_STORAGE_KEY = "webapp_theme_mode";
const OVERRIDE_VARS = [
  "--c-bg-rgb",
  "--c-surface-rgb",
  "--c-surface-2-rgb",
  "--c-text-rgb",
  "--c-text-muted-rgb",
  "--c-primary-rgb",
  "--c-primary-strong-rgb",
  "--c-primary-text-rgb",
  "--c-accent-rgb",
  "--c-danger-rgb",
];

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
  for (const name of OVERRIDE_VARS) root.removeProperty(name);
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
  const [mode, setModeState] = useState<ThemeMode>(() => (typeof window === "undefined" ? "auto" : readStoredMode()));
  const [scheme, setScheme] = useState<Scheme>(() =>
    typeof window === "undefined" ? "dark" : mode === "auto" ? detectSystemScheme() : mode
  );

  const setMode = useCallback((next: ThemeMode) => {
    setModeState(next);
    try {
      localStorage.setItem(MODE_STORAGE_KEY, next);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    const webApp = window.Telegram?.WebApp;

    const applyAuto = () => {
      const next = detectSystemScheme();
      setScheme(next);
      document.documentElement.setAttribute("data-theme", next);
      applyTelegramColors();
    };

    const applyForced = (forced: Scheme) => {
      clearInlineOverrides();
      setScheme(forced);
      document.documentElement.setAttribute("data-theme", forced);
    };

    if (mode === "auto") {
      applyAuto();
      if (webApp) {
        webApp.onEvent("themeChanged", applyAuto);
        return () => webApp.offEvent("themeChanged", applyAuto);
      }
      const media = window.matchMedia("(prefers-color-scheme: dark)");
      media.addEventListener("change", applyAuto);
      return () => media.removeEventListener("change", applyAuto);
    }

    applyForced(mode);
    return undefined;
  }, [mode]);

  return <ThemeContext.Provider value={{ scheme, mode, setMode }}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  return useContext(ThemeContext);
}

export function useColorScheme() {
  return useContext(ThemeContext).scheme;
}
