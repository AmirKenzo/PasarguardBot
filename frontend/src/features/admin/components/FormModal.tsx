import { useId, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { DialogShell, DialogTitleBar } from "../../../components/ui";

const SIZE_CLASSES = {
  md: "max-w-lg",
  xl: "max-w-3xl",
} as const;

export interface FormModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  size?: keyof typeof SIZE_CLASSES;
}

/** Like the UI kit's Modal, but wide enough for a multi-field form. */
export function FormModal({ open, onClose, title, children, size = "md" }: FormModalProps) {
  const { t } = useTranslation();
  const titleId = useId();
  return (
    <DialogShell
      open={open}
      onClose={onClose}
      labelledBy={titleId}
      className={`flex max-h-[85dvh] w-full ${SIZE_CLASSES[size]} flex-col overflow-hidden rounded-lg border border-border bg-surface p-5 shadow-lg`}
    >
      <DialogTitleBar id={titleId} title={title} onClose={onClose} closeLabel={t("common.close")} className="mb-4 shrink-0" />
      <div className="-mx-5 min-h-0 flex-1 overflow-y-auto px-5">{children}</div>
    </DialogShell>
  );
}
