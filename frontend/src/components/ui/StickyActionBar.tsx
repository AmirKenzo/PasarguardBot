import type { ReactNode } from "react";

export interface StickyActionBarProps {
  /** Small caption above the amount (e.g. "Final price"). */
  caption?: ReactNode;
  /** Main figure, usually a formatted price. */
  amount?: ReactNode;
  /** Action button(s). */
  children: ReactNode;
}

/**
 * Bottom action bar for checkout-like flows. On mobile it is fixed above the
 * bottom navigation (`--bottom-nav-h`, set by AppShell) and reserves its own
 * height with a spacer; on desktop it becomes a sticky card at the bottom of
 * the content column.
 */
export function StickyActionBar({ caption, amount, children }: StickyActionBarProps) {
  const hasSummary = caption != null || amount != null;
  return (
    <>
      <div aria-hidden="true" className="h-20 md:hidden" />
      <div className="fixed inset-x-0 z-20 border-t border-border bg-surface/95 px-4 py-3 backdrop-blur bottom-[var(--bottom-nav-h,0px)] md:sticky md:bottom-4 md:mt-4 md:rounded-lg md:border md:shadow-md">
        <div className="mx-auto flex max-w-3xl items-center gap-3">
          {hasSummary && (
            <div className="min-w-0 flex-1">
              {caption != null && <p className="truncate text-[11px] text-muted">{caption}</p>}
              {amount != null && <p className="truncate text-base font-extrabold text-text">{amount}</p>}
            </div>
          )}
          <div className={`flex items-center gap-2 ${hasSummary ? "shrink-0" : "flex-1 [&>*]:flex-1"}`}>{children}</div>
        </div>
      </div>
    </>
  );
}
