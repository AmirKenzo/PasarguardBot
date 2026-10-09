import { formatNumber } from "../../lib/format";

export interface ChipTabOption<T extends string | number> {
  value: T;
  label: string;
  count?: number;
}

export interface ChipTabsProps<T extends string | number> {
  options: ChipTabOption<T>[];
  value: T;
  onChange: (value: T) => void;
  className?: string;
}

/** Horizontally scrollable filter chips; the active chip is filled. */
export function ChipTabs<T extends string | number>({ options, value, onChange, className = "" }: ChipTabsProps<T>) {
  return (
    <div role="tablist" className={`no-scrollbar -mx-1 flex gap-1.5 overflow-x-auto px-1 ${className}`}>
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={String(opt.value)}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(opt.value)}
            className={`shrink-0 whitespace-nowrap rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors ${
              active ? "border-transparent bg-text text-bg" : "border-border bg-surface text-muted hover:text-text"
            }`}
          >
            {opt.label}
            {opt.count != null && <span className="ms-1 opacity-60">{formatNumber(opt.count)}</span>}
          </button>
        );
      })}
    </div>
  );
}
