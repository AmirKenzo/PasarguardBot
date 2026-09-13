import { forwardRef } from "react";
import type { SelectHTMLAttributes } from "react";

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectFieldProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  options: SelectOption[];
  hint?: string;
}

/** A plain dropdown — the UI kit's SegmentedControl does not scale to long lists. */
export const SelectField = forwardRef<HTMLSelectElement, SelectFieldProps>(function SelectField(
  { label, options, hint, className = "", id, ...rest },
  ref
) {
  const selectId = id || rest.name;
  return (
    <label className="block w-full text-sm" htmlFor={selectId}>
      {label && <span className="mb-1.5 block text-muted">{label}</span>}
      <select
        ref={ref}
        id={selectId}
        className={`h-11 w-full rounded-md border border-border bg-surface px-3 text-text outline-none transition-[border-color,box-shadow] duration-200 focus:border-primary focus:ring-4 focus:ring-primary/10 ${className}`}
        {...rest}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {hint && <span className="mt-1 block text-xs text-muted">{hint}</span>}
    </label>
  );
});
