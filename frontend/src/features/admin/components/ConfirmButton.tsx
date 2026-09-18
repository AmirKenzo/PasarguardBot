import { useState } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";
import { Button } from "../../../components/ui";
import type { ButtonProps } from "../../../components/ui";
import { useTranslation } from "react-i18next";
import { useAnchoredPopover } from "./useAnchoredPopover";

export interface ConfirmButtonProps extends Omit<ButtonProps, "onClick"> {
  /** Shown inside the confirmation popover. */
  message: ReactNode;
  confirmLabel?: string;
  onConfirm: () => void;
}

const POPOVER_WIDTH = 220;
// Message is at most a couple of short lines + one button row + padding.
const POPOVER_HEIGHT_ESTIMATE = 110;

/** A destructive or irreversible action, gated behind an explicit confirmation
 * shown in a small popover anchored to the button — not a full-screen modal,
 * so it stays next to whichever row/action it belongs to. */
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
  const { triggerRef, popoverRef, placement } = useAnchoredPopover<HTMLButtonElement>(
    open,
    () => setOpen(false),
    { width: POPOVER_WIDTH, heightEstimate: POPOVER_HEIGHT_ESTIMATE }
  );

  return (
    <>
      <Button ref={triggerRef} {...rest} onClick={() => setOpen((v) => !v)}>
        {children}
      </Button>
      {open &&
        placement &&
        createPortal(
          <div
            ref={popoverRef}
            role="dialog"
            style={{
              position: "fixed",
              top: placement.top,
              left: placement.left,
              width: POPOVER_WIDTH,
            }}
            className="z-50 rounded-lg border border-border bg-surface p-2.5 shadow-lg"
          >
            <p className="text-xs leading-snug text-text">{message}</p>
            <div className="mt-2 flex justify-end gap-1.5">
              <Button variant="ghost" size="sm" className="!h-7 !px-2 !text-xs" onClick={() => setOpen(false)}>
                {t("panel.common.dismiss")}
              </Button>
              <Button
                variant={rest.variant === "danger" ? "danger" : "primary"}
                size="sm"
                className="!h-7 !px-2 !text-xs"
                onClick={() => {
                  setOpen(false);
                  onConfirm();
                }}
              >
                {confirmText}
              </Button>
            </div>
          </div>,
          document.body
        )}
    </>
  );
}
