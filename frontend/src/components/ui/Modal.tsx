import { useId, type ReactNode } from "react";
import { AnimatePresence, m } from "framer-motion";
import { X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useDialogLayer } from "../../hooks/useDialogLayer";

const SIZE_CLASSES = {
  sm: "max-w-sm",
  lg: "max-w-2xl",
};

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
  size?: keyof typeof SIZE_CLASSES;
}

export function Modal({ open, onClose, title, children, size = "sm" }: ModalProps) {
  const { t } = useTranslation();
  const titleId = useId();
  useDialogLayer(open, onClose);
  return (
    <AnimatePresence>
      {open && (
        <>
          <m.div
            key="overlay"
            className="fixed inset-0 z-40 bg-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <div className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center p-4">
            <m.div
              key="panel"
              role="dialog"
              aria-modal="true"
              aria-labelledby={title ? titleId : undefined}
              className={`pointer-events-auto flex max-h-[85dvh] w-full ${SIZE_CLASSES[size]} flex-col overflow-hidden rounded-lg border border-border bg-surface p-5 shadow-lg`}
              initial={{ opacity: 0, scale: 0.94, y: 12 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 8 }}
              transition={{ type: "spring", stiffness: 380, damping: 30 }}
            >
              {title && (
                <div className="mb-3 flex shrink-0 items-center justify-between">
                  <h2 id={titleId} className="text-base font-semibold text-text">
                    {title}
                  </h2>
                  <button onClick={onClose} className="rounded-full p-1.5 text-muted hover:bg-surface-2" aria-label={t("ui.close")}>
                    <X size={18} />
                  </button>
                </div>
              )}
              <div className="-mx-5 min-h-0 flex-1 overflow-y-auto px-5">{children}</div>
            </m.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
}
