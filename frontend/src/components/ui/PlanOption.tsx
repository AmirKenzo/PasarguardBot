import type { ReactNode } from "react";

export interface PlanOptionProps {
  title: ReactNode;
  subtitle?: ReactNode;
  price?: ReactNode;
  /** Struck-through original price shown above `price`. */
  oldPrice?: ReactNode;
  /** Small tag next to the title (e.g. "Current plan"). */
  tag?: ReactNode;
  selected: boolean;
  disabled?: boolean;
  onSelect: () => void;
}

/** Radio-style selectable card used for plans, durations and volume packs. */
export function PlanOption({ title, subtitle, price, oldPrice, tag, selected, disabled, onSelect }: PlanOptionProps) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      disabled={disabled}
      onClick={onSelect}
      className={`flex w-full items-center gap-3 rounded-lg border-[1.5px] p-3.5 text-start transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
        selected ? "border-primary bg-primary/6" : "border-border bg-surface hover:border-primary/40"
      }`}
    >
      <span
        className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 ${
          selected ? "border-primary" : "border-muted/40"
        }`}
      >
        {selected && <span className="h-2.5 w-2.5 rounded-full bg-primary" />}
      </span>
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-center gap-1.5 text-base font-extrabold text-text">
          {title}
          {tag && (
            <span className="rounded-full bg-accent/14 px-2 py-0.5 text-[10px] font-bold text-accent">{tag}</span>
          )}
        </p>
        {subtitle && <p className="mt-0.5 text-[11px] text-muted">{subtitle}</p>}
      </div>
      {(price != null || oldPrice != null) && (
        <div className="shrink-0 text-end">
          {oldPrice != null && <p className="text-[10.5px] text-muted line-through">{oldPrice}</p>}
          {price != null && <p className="text-sm font-extrabold text-text">{price}</p>}
        </div>
      )}
    </button>
  );
}
