import type { ReactNode } from "react";
import { AnimatePresence, m } from "framer-motion";
import { X } from "lucide-react";
import { useDialogLayer } from "../../hooks/useDialogLayer";

const SPRING_CENTER = { type: "spring", stiffness: 380, damping: 30 } as const;
const SPRING_BOTTOM = { type: "spring", stiffness: 340, damping: 34 } as const;
const SPRING_RESPONSIVE = { type: "spring", stiffness: 380, damping: 32 } as const;
const DRAG_DISMISS_OFFSET = 120;

export type DialogPlacement = "center" | "bottom" | "responsive";

export interface DialogShellProps {
  open: boolean;
  onClose: () => void;
  placement?: DialogPlacement;
  labelledBy?: string;
  className?: string;
  children: ReactNode;
}

export function DialogShell({
  open,
  onClose,
  placement = "center",
  labelledBy,
  className = "",
  children,
}: DialogShellProps) {
  useDialogLayer(open, onClose);

  if (placement === "responsive") {
    if (!open) return null;
    return (
      <m.div
        className="fixed inset-0 z-50 flex items-end justify-center md:items-center md:p-4"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.15 }}
      >
        <div className="absolute inset-0 bg-overlay" onClick={onClose} />
        <m.div
          role="dialog"
          aria-modal="true"
          aria-labelledby={labelledBy}
          className={`relative ${className}`}
          initial={{ y: 24 }}
          animate={{ y: 0 }}
          transition={SPRING_RESPONSIVE}
        >
          {children}
        </m.div>
      </m.div>
    );
  }

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
          {placement === "bottom" ? (
            <m.div
              key="panel"
              role="dialog"
              aria-modal="true"
              aria-labelledby={labelledBy}
              className={`fixed inset-x-0 bottom-0 z-50 ${className}`}
              initial={{ y: "100%" }}
              animate={{ y: 0 }}
              exit={{ y: "100%" }}
              transition={SPRING_BOTTOM}
              drag="y"
              dragConstraints={{ top: 0, bottom: 0 }}
              dragElastic={{ top: 0, bottom: 0.4 }}
              onDragEnd={(_, info) => {
                if (info.offset.y > DRAG_DISMISS_OFFSET) onClose();
              }}
            >
              {children}
            </m.div>
          ) : (
            <div key="wrapper" className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center p-4">
              <m.div
                key="panel"
                role="dialog"
                aria-modal="true"
                aria-labelledby={labelledBy}
                className={`pointer-events-auto ${className}`}
                initial={{ opacity: 0, scale: 0.94, y: 12 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.96, y: 8 }}
                transition={SPRING_CENTER}
              >
                {children}
              </m.div>
            </div>
          )}
        </>
      )}
    </AnimatePresence>
  );
}

export interface DialogTitleBarProps {
  id: string;
  title: string;
  onClose: () => void;
  closeLabel: string;
  className?: string;
}

export function DialogTitleBar({ id, title, onClose, closeLabel, className = "mb-3" }: DialogTitleBarProps) {
  return (
    <div className={`flex items-center justify-between ${className}`}>
      <h2 id={id} className="text-base font-semibold text-text">
        {title}
      </h2>
      <button onClick={onClose} className="rounded-full p-1.5 text-muted hover:bg-surface-2" aria-label={closeLabel}>
        <X size={18} />
      </button>
    </div>
  );
}
