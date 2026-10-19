import { useId, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { DialogShell, DialogTitleBar } from "./DialogShell";

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
  return (
    <DialogShell
      open={open}
      onClose={onClose}
      labelledBy={title ? titleId : undefined}
      className={`flex max-h-[85dvh] w-full ${SIZE_CLASSES[size]} flex-col overflow-hidden rounded-lg border border-border bg-surface p-5 shadow-lg`}
    >
      {title && (
        <DialogTitleBar id={titleId} title={title} onClose={onClose} closeLabel={t("ui.close")} className="mb-3 shrink-0" />
      )}
      <div className="-mx-5 min-h-0 flex-1 overflow-y-auto px-5">{children}</div>
    </DialogShell>
  );
}
