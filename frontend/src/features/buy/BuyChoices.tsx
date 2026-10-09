import type { ReactNode } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Badge, IconBadge, Spinner } from "../../components/ui";

type Tone = "primary" | "success" | "warning" | "danger" | "muted" | "accent";

export function useForwardChevron(): LucideIcon {
  const { i18n } = useTranslation();
  return i18n.dir() === "rtl" ? ChevronLeft : ChevronRight;
}

export interface ChoiceCardProps {
  icon: LucideIcon;
  tone: Tone;
  title: string;
  description?: string;
  badge?: string;
  highlighted?: boolean;
  disabled?: boolean;
  loading?: boolean;
  onSelect?: () => void;
  children?: ReactNode;
}

/** A tappable option row: icon, title, one-line description and a forward chevron. */
export function ChoiceCard({
  icon,
  tone,
  title,
  description,
  badge,
  highlighted = false,
  disabled = false,
  loading = false,
  onSelect,
  children,
}: ChoiceCardProps) {
  const Forward = useForwardChevron();
  return (
    <div
      className={`overflow-hidden rounded-lg border bg-surface transition-colors ${
        highlighted ? "border-primary/40 bg-primary/5" : "border-border"
      } ${disabled ? "opacity-60" : ""}`}
    >
      <button
        type="button"
        disabled={disabled || loading}
        onClick={onSelect}
        className={`flex w-full items-center gap-3.5 p-4 text-start ${
          disabled ? "cursor-not-allowed" : "transition-colors hover:bg-surface-2/40"
        }`}
      >
        <IconBadge icon={icon} tone={tone} size="md" />
        <div className="min-w-0 flex-1">
          <p className="truncate font-bold text-text">{title}</p>
          {description && <p className="mt-0.5 truncate text-xs text-muted">{description}</p>}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {badge && <Badge tone="muted">{badge}</Badge>}
          {loading ? <Spinner size={16} /> : disabled ? null : <Forward size={16} className="text-muted" />}
        </div>
      </button>
      {children}
    </div>
  );
}

export function Banner({ tone, children }: { tone: "warning" | "danger"; children: ReactNode }) {
  const cls =
    tone === "warning" ? "border-warning/25 bg-warning/5 text-warning" : "border-danger/25 bg-danger/5 text-danger";
  return <p className={`rounded-md border px-4 py-3 text-sm ${cls}`}>{children}</p>;
}

/** A chosen value shown as a pill; tapping it goes back to change it. */
export function SelectionChip({ label, onChange }: { label: string; onChange: () => void }) {
  const { t } = useTranslation();
  return (
    <button
      type="button"
      onClick={onChange}
      className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-3 py-1.5 text-xs font-semibold text-text transition-colors hover:border-primary/40"
    >
      {label}
      <span className="font-medium text-primary">{t("ui.change")}</span>
    </button>
  );
}

export function InfoRow({ label, value, strong = false }: { label: string; value: ReactNode; strong?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 text-sm">
      <span className="text-muted">{label}</span>
      <span className={strong ? "font-extrabold text-primary" : "font-medium text-text"}>{value}</span>
    </div>
  );
}

export const STEP_MOTION = {
  initial: { opacity: 0, x: 16 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: -16 },
  transition: { duration: 0.18 },
} as const;
