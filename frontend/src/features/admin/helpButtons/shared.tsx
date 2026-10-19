import { Check, Link2, MessageSquareText, Package } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { HelpButtonKind, PanelHelpButton } from "../../../types/panel";
import { COLOUR_OPTIONS, styleLabels, SWATCH_CLASSES } from "../keyboard/shared";

export const HELP_QUERY_KEY = ["help-buttons"];
export const HELP_INVALIDATE = [HELP_QUERY_KEY];

/** The bot keeps at most this many buttons on one row. */
export const MAX_PER_ROW = 8;

export const KIND_ICONS: Record<HelpButtonKind, LucideIcon> = {
  link: Link2,
  app: Package,
  text: MessageSquareText,
};

/** Rendered colour for a stored style: anything outside the offered colours draws plain. */
export function chipStyle(style: string | null | undefined): string {
  return style && style !== "none" && (COLOUR_OPTIONS as readonly string[]).includes(style) ? style : "";
}

export function styleDraft(style: string | null | undefined): string {
  return chipStyle(style) || "none";
}

export function buttonTitle(button: PanelHelpButton | undefined, fallback: string): string {
  return button?.text?.trim() || fallback;
}

/** Stable fingerprint of a layout. */
export function layoutSignature(layout: number[][]): string {
  return JSON.stringify(layout.filter((row) => row.length > 0));
}

/**
 * Keep the admin's unsaved rows, drop buttons that no longer exist and give
 * buttons the draft doesn't know yet a row of their own, in server order.
 */
export function mergeLayout(draft: number[][], server: number[][], ids: Set<number>): number[][] {
  const kept = draft.map((row) => row.filter((id) => ids.has(id))).filter((row) => row.length > 0);
  const seen = new Set(kept.flat());
  for (const row of server) {
    const fresh = row.filter((id) => !seen.has(id));
    if (fresh.length) {
      kept.push(fresh);
      fresh.forEach((id) => seen.add(id));
    }
  }
  return kept;
}

export function ColourPicker({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const { t } = useTranslation();
  const labels = styleLabels(t);
  return (
    <div className="flex flex-wrap gap-2">
      {COLOUR_OPTIONS.map((option) => {
        const active = value === option;
        return (
          <button
            key={option}
            type="button"
            onClick={() => onChange(option)}
            className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1.5 text-xs font-medium transition-colors ${
              active ? "border-primary/50 bg-primary/10 text-text" : "border-border text-muted hover:text-text"
            }`}
          >
            <span className={`h-3.5 w-3.5 rounded-full ${SWATCH_CLASSES[option]}`} />
            {option === "none" ? t("panel.helpButtons.noColour") : labels[option]}
            {active && <Check size={12} className="text-primary" />}
          </button>
        );
      })}
    </div>
  );
}

export const TEXTAREA_CLASS =
  "w-full rounded-md border border-border bg-surface p-3 text-sm text-text outline-none placeholder:text-muted focus:border-primary focus:ring-4 focus:ring-primary/10";
