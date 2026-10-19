import { useEffect, useId, useRef } from "react";
import type { LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button, DialogShell } from "../../../components/ui";

export interface ChoiceAction {
  label: string;
  variant: "primary" | "ghost" | "danger";
  loading?: boolean;
  onClick: () => void;
}

export interface ChoiceDialogProps {
  open: boolean;
  tone: "warning" | "danger";
  icon: LucideIcon;
  title: string;
  text: string;
  actions: ChoiceAction[];
  onClose: () => void;
}

const TONE_CLASSES = {
  warning: "bg-warning/12 text-warning",
  danger: "bg-danger/12 text-danger",
};

/**
 * A centered dialog on wide screens and a bottom sheet on phones, with an always-present cancel.
 * It unmounts as soon as it closes (no exit animation), so a finished dialog can never linger
 * invisibly on top of the page and swallow clicks.
 */
export function ChoiceDialog({ open, tone, icon: Icon, title, text, actions, onClose }: ChoiceDialogProps) {
  const { t } = useTranslation();
  const actionsRef = useRef<HTMLDivElement>(null);
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    const frame = requestAnimationFrame(() => actionsRef.current?.querySelector("button")?.focus());
    return () => cancelAnimationFrame(frame);
  }, [open]);

  return (
    <DialogShell
      open={open}
      onClose={onClose}
      placement="responsive"
      labelledBy={titleId}
      className="safe-area-pb max-h-[85dvh] w-full overflow-y-auto rounded-t-md border border-border bg-surface p-5 shadow-lg md:max-w-md md:rounded-md"
    >
      <span className={`mb-3 flex h-11 w-11 items-center justify-center rounded-sm ${TONE_CLASSES[tone]}`}>
        <Icon size={22} />
      </span>
      <h3 id={titleId} className="text-base font-semibold text-text">
        {title}
      </h3>
      <p className="mt-1 text-sm leading-relaxed text-muted">{text}</p>
      <div ref={actionsRef} className="mt-5 flex gap-2">
        {actions.map((action) => (
          <Button
            key={action.label}
            size="sm"
            variant={action.variant}
            loading={action.loading}
            className="flex-1"
            onClick={action.onClick}
          >
            {action.label}
          </Button>
        ))}
        <Button size="sm" variant="ghost" className="flex-1" onClick={onClose}>
          {t("panel.texts.cancel")}
        </Button>
      </div>
    </DialogShell>
  );
}
