import { useEffect, useRef } from "react";
import type { LucideIcon } from "lucide-react";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { Button } from "../../../components/ui";

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

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    requestAnimationFrame(() => actionsRef.current?.querySelector("button")?.focus());
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-end justify-center md:items-center md:p-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.15 }}
    >
      <div className="absolute inset-0 bg-overlay" onClick={onClose} />
      <motion.div
        role="dialog"
        aria-modal="true"
        aria-labelledby="choice-dialog-title"
        className="safe-area-pb relative w-full rounded-t-2xl border border-border bg-surface p-5 shadow-lg md:max-w-md md:rounded-2xl"
        initial={{ y: 24 }}
        animate={{ y: 0 }}
        transition={{ type: "spring", stiffness: 380, damping: 32 }}
      >
        <span className={`mb-3 flex h-11 w-11 items-center justify-center rounded-xl ${TONE_CLASSES[tone]}`}>
          <Icon size={22} />
        </span>
        <h3 id="choice-dialog-title" className="text-base font-semibold text-text">
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
      </motion.div>
    </motion.div>
  );
}
