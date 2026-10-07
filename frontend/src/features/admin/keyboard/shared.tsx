import type { ReactNode } from "react";
import type { TFunction } from "i18next";
import type { PanelKeyboardButton } from "../../../types/panel";

export type TabKey = "layout" | "buttons" | "emoji";

export const KEYBOARD_QUERY_KEY = ["keyboard"];
export const INVALIDATE = [KEYBOARD_QUERY_KEY];

export const sectionLabels = (t: TFunction): Record<string, string> => ({
  main_menu: t("panel.keyboard.mainMenu"),
  my_services: t("panel.keyboard.myServices"),
  balance: t("panel.common.addBalance"),
  buy: t("panel.keyboard.buyService"),
  reseller: t("panel.keyboard.reseller"),
  other: t("panel.keyboard.other"),
});

// Why the bot will not render a button, whatever the admin's switch says.
export const blockedLabels = (t: TFunction): Record<string, string> => ({
  no_shop_panel: t("panel.keyboard.blockedNoShopPanel"),
  reseller_sale_off: t("panel.keyboard.blockedResellerOff"),
  trial_off: t("panel.keyboard.blockedTrialOff"),
  miniapp_only: t("panel.keyboard.blockedMiniappOnly"),
  setting_off: t("panel.keyboard.blockedBySetting"),
  uptime_disabled: t("panel.keyboard.blockedUptime"),
});

/** Colours offered per button; "none" is the default and means no colour. */
export const COLOUR_OPTIONS = ["none", "primary", "success", "danger"] as const;

export const styleLabels = (t: TFunction): Record<string, string> => ({
  none: t("panel.common.default"),
  primary: t("panel.common.blue"),
  success: t("panel.common.green"),
  danger: t("panel.common.red"),
});

/** Chip classes per rendered colour, shared by the preview and the editors. */
export const STYLE_CLASSES: Record<string, string> = {
  primary: "border-primary/35 bg-primary/15 text-primary",
  success: "border-success/35 bg-success/15 text-success",
  danger: "border-danger/35 bg-danger/15 text-danger",
  glass: "border-white/25 bg-white/5 text-text backdrop-blur",
  "": "border-border bg-surface-2 text-text",
};

/** Swatch colour for the colour picker. */
export const SWATCH_CLASSES: Record<string, string> = {
  none: "bg-surface-2 ring-1 ring-inset ring-border",
  primary: "bg-primary",
  success: "bg-success",
  danger: "bg-danger",
};

/**
 * The colour Telegram will actually draw. A null style falls back to the
 * built-in default, an empty stored style means "no colour".
 */
export function renderedStyle(button: PanelKeyboardButton | undefined, glassMode = false, draftStyle?: string): string {
  if (!button) return "";
  if (glassMode && button.in_home) return "glass";
  if (draftStyle !== undefined) return draftStyle === "none" ? "" : draftStyle;
  if (button.style == null) return button.default_style || "";
  return button.style;
}

export function buttonLabel(button: PanelKeyboardButton | undefined, fallback = ""): string {
  return button?.text || button?.default_text || button?.title || fallback;
}

/**
 * Picker value for the colour the button shows today. Anything outside the
 * offered colours (unset, cleared, legacy glass) reads as "none".
 */
export function styleDraftOf(button: PanelKeyboardButton): string {
  const style = button.style == null ? button.default_style : button.style;
  return (COLOUR_OPTIONS as readonly string[]).includes(style || "") ? (style as string) : "none";
}

export function isCustomized(button: PanelKeyboardButton): boolean {
  return Boolean(button.text) || button.style != null || button.icon != null;
}

export function ButtonChip({
  label,
  style,
  icon,
  className = "",
}: {
  label: string;
  style: string;
  icon?: boolean;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex min-w-0 items-center justify-center gap-1 truncate rounded-md border px-2.5 py-1.5 text-xs font-medium ${
        STYLE_CLASSES[style] ?? STYLE_CLASSES[""]
      } ${className}`}
    >
      {icon && <span aria-hidden>✨</span>}
      <span className="truncate">{style === "glass" ? `[ ${label} ]` : label}</span>
    </span>
  );
}

export function Hint({ children }: { children: ReactNode }) {
  return <p className="text-xs leading-relaxed text-muted">{children}</p>;
}
