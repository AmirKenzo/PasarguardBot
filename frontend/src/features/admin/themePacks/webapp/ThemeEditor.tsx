import { useState } from "react";
import type { ChangeEvent } from "react";
import { Moon, Sparkles, Sun, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button, Card, Input } from "../../../../components/ui";
import {
  MAX_BORDER_ALPHA,
  MAX_RADIUS,
  MIN_RADIUS,
  contrast,
  fixContrast,
  generateTheme,
  hexToHsl,
  hslToHex,
  isHex,
  onColor,
} from "../../../../design/webappThemes";
import type { PaletteKey, Scheme, WebappTheme } from "../../../../design/webappThemes";
import { COLOR_GROUPS, CONTRAST_CHECKS } from "./shared";

/** Hues offered as one-click starting points. */
const QUICK_HUES = [212, 196, 158, 84, 38, 22, 352, 330, 262, 235];

export interface ThemeDraft {
  /** Library id being edited; null for a new theme. */
  themeId: number | null;
  name: string;
  theme: WebappTheme;
  dirty: boolean;
}

export interface ThemeEditorProps {
  draft: ThemeDraft;
  scheme: Scheme;
  onSchemeChange: (scheme: Scheme) => void;
  onChange: (draft: ThemeDraft) => void;
  onCancel: () => void;
  onSave: (activate: boolean) => void;
  saving: boolean;
}

function HexField({ value, label, onCommit }: { value: string; label: string; onCommit: (hex: string) => void }) {
  const [text, setText] = useState(value);
  const [focused, setFocused] = useState(false);
  const shown = focused ? text : value;
  const normalized = shown.startsWith("#") ? shown : `#${shown}`;
  const bad = shown.length >= 6 && !isHex(normalized);

  return (
    <input
      value={shown}
      maxLength={7}
      spellCheck={false}
      aria-label={label}
      onFocus={() => {
        setText(value);
        setFocused(true);
      }}
      onBlur={() => setFocused(false)}
      onChange={(event) => {
        const next = event.target.value.trim();
        setText(next);
        const hex = next.startsWith("#") ? next : `#${next}`;
        if (isHex(hex)) onCommit(hex.toLowerCase());
      }}
      className={`ltr-field h-8 w-full rounded-sm border bg-surface-2 px-2 font-mono text-xs lowercase text-text outline-none focus:border-primary ${
        bad ? "border-danger" : "border-border"
      }`}
    />
  );
}

export function ThemeEditor({ draft, scheme, onSchemeChange, onChange, onCancel, onSave, saving }: ThemeEditorProps) {
  const { t } = useTranslation();
  const palette = draft.theme[scheme];
  const k = (key: string, options?: Record<string, unknown>) => t(`panel.webappThemes.editor.${key}`, options);

  const update = (theme: WebappTheme, name = draft.name) => onChange({ ...draft, name, theme, dirty: true });

  const setColor = (key: PaletteKey, hex: string) => {
    const next = { ...palette, [key]: hex };
    // Moving the brand color keeps the button label readable on it.
    if (key === "primary") next.primary_text = onColor(hex);
    update({ ...draft.theme, [scheme]: next });
  };

  const regenerate = (hue: number, sat = 80) => {
    const generated = generateTheme({ hue, sat, radius: draft.theme.radius });
    update(generated);
  };

  const pickSeed = (event: ChangeEvent<HTMLInputElement>) => {
    const [hue, sat] = hexToHsl(event.target.value);
    regenerate(hue, Math.min(90, Math.max(12, sat)));
  };

  return (
    <Card className="flex flex-col gap-5 p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold text-text">{draft.themeId ? k("editTitle") : k("newTitle")}</h2>
          <p className="text-xs text-muted">{k("hint")}</p>
        </div>
        <Button size="sm" variant="ghost" onClick={onCancel} aria-label={t("common.cancel")}>
          <X size={16} />
        </Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
        <Input
          label={k("name")}
          value={draft.name}
          maxLength={100}
          onChange={(event) => onChange({ ...draft, name: event.target.value, dirty: true })}
        />
        <div className="flex flex-col gap-1.5">
          <span className="text-xs font-medium text-muted">{k("editing")}</span>
          <div className="inline-flex rounded-md border border-border bg-surface-2 p-1">
            {(["light", "dark"] as const).map((value) => (
              <button
                key={value}
                type="button"
                aria-pressed={scheme === value}
                onClick={() => onSchemeChange(value)}
                className={`flex items-center gap-1.5 rounded-sm px-3 py-1.5 text-xs font-semibold transition-colors ${
                  scheme === value ? "bg-surface text-text shadow-sm" : "text-muted"
                }`}
              >
                {value === "light" ? <Sun size={14} /> : <Moon size={14} />}
                {t(`panel.webappThemes.${value}`)}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 rounded-md border border-primary/20 bg-primary/6 p-3">
        <div className="min-w-[180px] flex-1">
          <p className="flex items-center gap-1.5 text-sm font-semibold text-text">
            <Sparkles size={15} className="text-primary" />
            {k("quickTitle")}
          </p>
          <p className="text-xs text-muted">{k("quickText")}</p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {QUICK_HUES.map((hue) => (
            <button
              key={hue}
              type="button"
              onClick={() => regenerate(hue)}
              aria-label={k("quickHue", { hue })}
              className="h-7 w-7 rounded-full ring-2 ring-surface ring-offset-1 ring-offset-border transition-transform hover:scale-110"
              style={{ background: hslToHex(hue, 80, 52) }}
            />
          ))}
          <label
            className="relative h-7 w-7 cursor-pointer overflow-hidden rounded-full ring-2 ring-surface ring-offset-1 ring-offset-border"
            style={{ background: "conic-gradient(red, yellow, lime, cyan, blue, magenta, red)" }}
            title={k("quickCustom")}
          >
            <input type="color" onChange={pickSeed} className="absolute inset-0 h-full w-full cursor-pointer opacity-0" />
          </label>
        </div>
      </div>

      <div className="grid gap-x-5 gap-y-4 md:grid-cols-2">
        {COLOR_GROUPS.map((group) => (
          <div key={group.key} className="flex min-w-0 flex-col gap-1">
            <span className="text-xs font-semibold text-muted">{k(`groups.${group.key}`)}</span>
            {group.colors.map((key) => (
              <div
                key={key}
                className="grid grid-cols-[34px_minmax(0,1fr)_88px] items-center gap-2.5 rounded-sm p-1.5 hover:bg-surface-2"
              >
                <label
                  className="relative h-[34px] w-[34px] cursor-pointer overflow-hidden rounded-xs ring-1 ring-inset ring-black/15"
                  style={{ background: palette[key] }}
                >
                  <input
                    type="color"
                    value={palette[key]}
                    onChange={(event) => setColor(key, event.target.value.toLowerCase())}
                    aria-label={k(`colors.${key}.title`)}
                    className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
                  />
                </label>
                <div className="min-w-0">
                  <p className="text-xs-plus font-semibold leading-tight text-text">{k(`colors.${key}.title`)}</p>
                  <p className="text-2xs leading-snug text-muted">{k(`colors.${key}.text`)}</p>
                </div>
                <HexField
                  value={palette[key]}
                  label={k("hexOf", { name: k(`colors.${key}.title`) })}
                  onCommit={(hex) => setColor(key, hex)}
                />
              </div>
            ))}
          </div>
        ))}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <label className="flex flex-col gap-1.5">
          <span className="flex justify-between text-sm font-medium text-text">
            {k("radius")}
            <span className="ltr-field font-mono text-xs text-muted">{draft.theme.radius}px</span>
          </span>
          <input
            type="range"
            min={MIN_RADIUS}
            max={MAX_RADIUS}
            value={draft.theme.radius}
            onChange={(event) => update({ ...draft.theme, radius: Number(event.target.value) })}
            className="w-full accent-[rgb(var(--c-primary-rgb))]"
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="flex justify-between text-sm font-medium text-text">
            {k("border", { scheme: t(`panel.webappThemes.${scheme}`) })}
            <span className="ltr-field font-mono text-xs text-muted">{Math.round(palette.border_alpha * 100)}%</span>
          </span>
          <input
            type="range"
            min={0}
            max={Math.round(MAX_BORDER_ALPHA * 100)}
            value={Math.round(palette.border_alpha * 100)}
            onChange={(event) =>
              update({ ...draft.theme, [scheme]: { ...palette, border_alpha: Number(event.target.value) / 100 } })
            }
            className="w-full accent-[rgb(var(--c-primary-rgb))]"
          />
        </label>
      </div>

      <div className="flex flex-col gap-1.5">
        <span className="text-xs font-semibold text-muted">
          {k("readability", { scheme: t(`panel.webappThemes.${scheme}`) })}
        </span>
        {CONTRAST_CHECKS.map((check) => {
          const ratio = contrast(palette[check.fg], palette[check.bg]);
          const ok = ratio >= check.min;
          return (
            <div
              key={check.label}
              className="grid grid-cols-[40px_minmax(0,1fr)_auto_auto] items-center gap-2.5 rounded-sm bg-surface-2 px-2.5 py-1.5"
            >
              <span
                className="flex h-6 items-center justify-center rounded-xs text-xs-plus font-extrabold ring-1 ring-inset ring-black/10"
                style={{ background: palette[check.bg], color: palette[check.fg] }}
              >
                {k("sample")}
              </span>
              <span className="min-w-0 text-xs text-text">{k(`checks.${check.label}`)}</span>
              <span className="ltr-field font-mono text-2xs text-muted">{ratio.toFixed(1)} : 1</span>
              {ok ? (
                <span className="rounded-full bg-success/14 px-2 py-0.5 text-2xs font-bold text-success">{k("readable")}</span>
              ) : (
                <button
                  type="button"
                  onClick={() => setColor(check.fg, fixContrast(palette[check.fg], palette[check.bg], check.min + 0.1))}
                  className="rounded-full bg-danger/14 px-2 py-0.5 text-2xs font-bold text-danger hover:bg-danger/20"
                >
                  {k("fix")}
                </button>
              )}
            </div>
          );
        })}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-4">
        <span className="text-xs font-semibold text-warning">{draft.dirty ? k("unsaved") : ""}</span>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" loading={saving} onClick={() => onSave(false)}>
            {k("save")}
          </Button>
          <Button size="sm" loading={saving} onClick={() => onSave(true)}>
            {k("saveActivate")}
          </Button>
        </div>
      </div>
    </Card>
  );
}
