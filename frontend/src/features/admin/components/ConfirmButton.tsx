import { useState } from "react";
import type { ReactNode } from "react";
import { Button, Modal } from "../../../components/ui";
import type { ButtonProps } from "../../../components/ui";
import { useTranslation } from "react-i18next";

export interface ConfirmButtonProps extends Omit<ButtonProps, "onClick"> {
  /** Shown inside the confirmation dialog. */
  message: ReactNode;
  confirmLabel?: string;
  onConfirm: () => void;
}

/** A destructive or irreversible action, gated behind an explicit confirmation. */
export function ConfirmButton({
  message,
  confirmLabel,
  onConfirm,
  children,
  ...rest
}: ConfirmButtonProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const confirmText = confirmLabel ?? t("panel.common.confirm");

  return (
    <>
      <Button {...rest} onClick={() => setOpen(true)}>
        {children}
      </Button>
      <Modal open={open} onClose={() => setOpen(false)} title={t("panel.confirmButton.confirm")}>
        <div className="space-y-4">
          <p className="text-sm text-text">{message}</p>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>
              {t("panel.common.dismiss")}
            </Button>
            <Button
              variant={rest.variant === "danger" ? "danger" : "primary"}
              size="sm"
              onClick={() => {
                setOpen(false);
                onConfirm();
              }}
            >
              {confirmText}
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}
