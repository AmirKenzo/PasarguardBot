import { useEffect, useRef, useState } from "react";

export interface AnchoredPlacement {
  top: number;
  left: number;
}

export interface UseAnchoredPopoverOptions {
  width: number;
  heightEstimate: number;
  align?: "center" | "start" | "end";
}

const VIEWPORT_MARGIN = 8;


export function useAnchoredPopover<T extends HTMLElement = HTMLButtonElement>(
  open: boolean,
  onClose: () => void,
  { width, heightEstimate, align = "center" }: UseAnchoredPopoverOptions
) {
  const triggerRef = useRef<T>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const [placement, setPlacement] = useState<AnchoredPlacement | null>(null);

  useEffect(() => {
    if (!open) {
      setPlacement(null);
      return;
    }
    function place() {
      const rect = triggerRef.current?.getBoundingClientRect();
      if (!rect) return;
      let left =
        align === "start" ? rect.left : align === "end" ? rect.right - width : rect.left + rect.width / 2 - width / 2;
      left = Math.min(Math.max(left, VIEWPORT_MARGIN), window.innerWidth - width - VIEWPORT_MARGIN);

      const spaceBelow = window.innerHeight - rect.bottom;
      const fitsBelow = spaceBelow >= heightEstimate + VIEWPORT_MARGIN;
      let top = fitsBelow ? rect.bottom + 6 : rect.top - 6 - heightEstimate;
      top = Math.min(Math.max(top, VIEWPORT_MARGIN), window.innerHeight - heightEstimate - VIEWPORT_MARGIN);
      setPlacement({ top, left });
    }
    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [open, width, heightEstimate, align]);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(e: PointerEvent) {
      const target = e.target as Node;
      if (popoverRef.current?.contains(target) || triggerRef.current?.contains(target)) return;
      onClose();
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open, onClose]);

  return { triggerRef, popoverRef, placement };
}
