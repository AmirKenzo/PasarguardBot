import { forwardRef } from "react";
import type { InputHTMLAttributes, ReactNode } from "react";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string | null;
  suffix?: ReactNode;
  ltr?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, error, suffix, ltr = false, className = "", id, ...rest },
  ref
) {
  const inputId = id || rest.name;
  return (
    <label className="block w-full text-sm" htmlFor={inputId}>
      {label && <span className="mb-1.5 block text-text-muted text-muted">{label}</span>}
      <span className="relative flex items-center">
        <input
          ref={ref}
          id={inputId}
          className={`h-11 w-full rounded-md border bg-surface px-3.5 text-text placeholder:text-muted outline-none transition-[border-color,box-shadow] duration-200 focus:border-primary focus:ring-4 ${
            error ? "border-danger focus:ring-danger/10" : "border-border focus:ring-primary/10"
          } ${suffix ? "pl-10" : ""} ${ltr ? "ltr-field" : ""} ${className}`}
          {...rest}
        />
        {suffix && <span className="absolute left-3 text-muted">{suffix}</span>}
      </span>
      {error && <span className="mt-1 block text-xs text-danger">{error}</span>}
    </label>
  );
});
