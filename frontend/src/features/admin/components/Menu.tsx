import { useState } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";
import { Check } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useAnchoredPopover } from "./useAnchoredPopover";

export interface IconMenuButtonProps {
  icon: LucideIcon;
  title: string;
  active?: boolean;
  badge?: boolean;
  spin?: boolean;
  width: number;
  /** Rough expected panel height, used only to decide placement/clamping. */
  heightEstimate: number;
  align?: "center" | "start" | "end";
  children: (close: () => void) => ReactNode;
}

/** A small icon button that opens a compact dropdown panel anchored to it.
 * Rendered through a portal so `position: fixed` is always relative to the
 * real viewport, not whatever animated wrapper (e.g. page transitions) the
 * button happens to sit inside. */
export function IconMenuButton({ icon: Icon, title, active, badge, spin, width, heightEstimate, align, children }: IconMenuButtonProps) {
  const [open, setOpen] = useState(false);
  const { triggerRef, popoverRef, placement } = useAnchoredPopover<HTMLButtonElement>(
    open,
    () => setOpen(false),
    { width, heightEstimate, align }
  );

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        title={title}
        onClick={() => setOpen((v) => !v)}
        className={`relative flex h-8 w-8 shrink-0 items-center justify-center rounded-md border transition-colors ${
          active ? "border-primary/40 bg-primary/12 text-primary" : "border-border text-muted hover:bg-surface-2 hover:text-text"
        }`}
      >
        <Icon size={14} className={spin ? "animate-spin" : undefined} />
        {badge && <span className="absolute -top-0.5 h-1.5 w-1.5 rounded-full bg-primary ltr:-right-0.5 rtl:-left-0.5" />}
      </button>
      {open &&
        placement &&
        createPortal(
          <div
            ref={popoverRef}
            role="menu"
            style={{ position: "fixed", top: placement.top, left: placement.left, width }}
            className="z-50 max-h-[70vh] overflow-y-auto rounded-lg border border-border bg-surface py-1.5 shadow-lg"
          >
            {children(() => setOpen(false))}
          </div>,
          document.body
        )}
    </>
  );
}

export function MenuHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="px-3 pb-1.5">
      <p className="text-[11px] font-semibold text-muted">{title}</p>
      {subtitle && <p className="text-xs text-text">{subtitle}</p>}
    </div>
  );
}

export function MenuDivider() {
  return <div className="border-t border-border" />;
}

export function MenuRow({
  icon: Icon,
  label,
  active,
  onClick,
}: {
  icon?: LucideIcon;
  label: string;
  active?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      role="menuitemradio"
      aria-checked={active}
      onClick={onClick}
      className={`flex w-full items-center gap-2 px-3 py-2 text-xs transition-colors ${
        active ? "text-primary" : "text-text hover:bg-surface-2"
      }`}
    >
      {Icon && <Icon size={13} className="shrink-0" />}
      <span className="flex-1 text-start">{label}</span>
      {active && <Check size={13} className="shrink-0" />}
    </button>
  );
}
