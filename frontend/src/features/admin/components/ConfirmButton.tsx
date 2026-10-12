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
  requireText?: string;
  requireTextLabel?: string;
}

const POPOVER_WIDTH = 220;
// Message is at most a couple of short lines + one button row + padding.
const POPOVER_HEIGHT_ESTIMATE = 110;
const TYPED_POPOVER_HEIGHT_ESTIMATE = 180;

function matchesRequired(typed: string, required: string): boolean {
  return typed.trim().toLowerCase() === required.trim().toLowerCase();
}

/** A destructive or irreversible action, gated behind an explicit confirmation
 * shown in a small popover anchored to the button — not a full-screen modal,
 * so it stays next to whichever row/action it belongs to. */
export function ConfirmButton({
  message,
  confirmLabel,
  onConfirm,
  requireText,
  requireTextLabel,
  children,
  ...rest
}: ConfirmButtonProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const confirmText = confirmLabel ?? t("panel.common.confirm");
  const canConfirm = requireText === undefined || matchesRequired(typed, requireText);
  const close = () => {
    setOpen(false);
    setTyped("");
  };
  const { triggerRef, popoverRef, placement } = useAnchoredPopover<HTMLButtonElement>(open, close, {
    width: POPOVER_WIDTH,
    heightEstimate: requireText === undefined ? POPOVER_HEIGHT_ESTIMATE : TYPED_POPOVER_HEIGHT_ESTIMATE,
  });

  return (
    <>
      <Button ref={triggerRef} {...rest} onClick={() => (open ? close() : setOpen(true))}>
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
            {requireText !== undefined && (
              <label className="mt-2 block text-xs">
                {requireTextLabel && <span className="mb-1 block text-muted">{requireTextLabel}</span>}
                <input
                  autoFocus
                  autoComplete="off"
                  spellCheck={false}
                  value={typed}
                  onChange={(event) => setTyped(event.target.value)}
                  placeholder={requireText}
                  className="ltr-field h-7 w-full rounded-md border border-border bg-surface px-2 text-xs text-text outline-none placeholder:text-muted/60 focus:border-danger"
                />
              </label>
            )}
            <div className="mt-2 flex justify-end gap-1.5">
              <Button variant="ghost" size="sm" className="!h-7 !px-2 !text-xs" onClick={close}>
                {t("panel.common.dismiss")}
              </Button>
              <Button
                variant={rest.variant === "danger" ? "danger" : "primary"}
                size="sm"
                className="!h-7 !px-2 !text-xs"
                disabled={!canConfirm}
                onClick={() => {
                  close();
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
