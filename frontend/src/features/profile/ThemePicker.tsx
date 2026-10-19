import { Check } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useTheme } from "../../design/ThemeProvider";
import { PICK_ADMIN, PICK_TELEGRAM, activeTheme } from "../../design/webappThemeConfig";
import { THEME_PRESETS } from "../../design/webappThemes";
import type { WebappTheme } from "../../design/webappThemes";

interface Option {
  id: string;
  name: string;
  theme: WebappTheme | null;
}

function Swatch({ theme, scheme }: { theme: WebappTheme | null; scheme: "light" | "dark" }) {
  if (!theme) {
    // Telegram's own colors: shown as the Telegram blue, split light/dark.
    return <span className="h-9 w-9 rounded-full bg-[linear-gradient(135deg,#ffffff_50%,#17212b_50%)] ring-1 ring-inset ring-border" />;
  }
  const p = theme[scheme];
  return (
    <span
      className="relative h-9 w-9 overflow-hidden rounded-full ring-1 ring-inset ring-black/10"
      style={{ background: `linear-gradient(135deg, ${p.bg} 50%, ${p.surface} 50%)` }}
    >
      <span
        className="absolute inset-[9px] rounded-full"
        style={{ background: `linear-gradient(135deg, ${p.primary}, ${p.accent})` }}
      />
    </span>
  );
}

/** Lets a user choose their own colors from the themes the admin offers (only shown when allowed). */
export function ThemePicker() {
  const { t } = useTranslation();
  const { config, pick, setPick, scheme } = useTheme();
  if (!config.user_pick) return null;

  const options: Option[] = [
    { id: PICK_ADMIN, name: t("profile.theme.botDefault"), theme: activeTheme(config) },
    { id: PICK_TELEGRAM, name: t("profile.theme.telegram"), theme: null },
    ...config.choices.map((choice) => ({ id: choice.id, name: choice.name, theme: choice.theme })),
    ...THEME_PRESETS.map((preset) => ({
      id: preset.id,
      name: t(`webappTheme.presets.${preset.id}`, { defaultValue: preset.id }),
      theme: preset.theme,
    })),
  ];
  const selected = options.some((option) => option.id === pick) ? pick : PICK_ADMIN;

  return (
    <div className="rounded-lg border border-border bg-surface p-3">
      <div className="no-scrollbar -mx-1 flex gap-1 overflow-x-auto px-1" role="radiogroup" aria-label={t("profile.theme.title")}>
        {options.map((option) => {
          const active = option.id === selected;
          return (
            <button
              key={option.id || "admin"}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => setPick(option.id)}
              className={`flex w-[72px] shrink-0 flex-col items-center gap-1.5 rounded-md px-1 py-2 transition-colors ${
                active ? "bg-primary/10" : "hover:bg-surface-2"
              }`}
            >
              <span className="relative">
                <Swatch theme={option.theme} scheme={scheme} />
                {active && (
                  <span className="absolute -bottom-0.5 -end-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-primary text-primary-text ring-2 ring-surface">
                    <Check size={10} strokeWidth={3} />
                  </span>
                )}
              </span>
              <span className={`line-clamp-2 text-center text-3xs leading-tight ${active ? "font-bold text-text" : "text-muted"}`}>
                {option.name}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
