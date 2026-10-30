import { useId, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { DialogShell, DialogTitleBar } from "./DialogShell";

export interface SheetProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  /** Small muted line under the title. */
  subtitle?: string;
  children: ReactNode;
  /** Kept at the bottom of the sheet while the content scrolls (e.g. the main action). */
  footer?: ReactNode;
}

export function Sheet({ open, onClose, title, subtitle, children, footer }: SheetProps) {
  const { t } = useTranslation();
  const titleId = useId();
  return (
    <DialogShell
      open={open}
      onClose={onClose}
      placement="bottom"
      labelledBy={title ? titleId : undefined}
      className="max-h-[86vh] overflow-y-auto rounded-t-lg border-t border-border bg-surface px-4 pb-[calc(1.25rem+env(safe-area-inset-bottom))] pt-3 shadow-lg"
    >
      <div className="mx-auto mb-2 h-1.5 w-10 rounded-full bg-surface-2" />
      {title && <DialogTitleBar id={titleId} title={title} onClose={onClose} closeLabel={t("ui.close")} />}
      {subtitle && <p className="-mt-1 mb-3 truncate text-xs text-muted">{subtitle}</p>}
      {children}
      {footer && <div className="sticky bottom-0 -mx-4 mt-4 border-t border-border bg-surface px-4 pt-3">{footer}</div>}
    </DialogShell>
  );
}
