import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { Sheet } from "../../../components/ui";
import type { PanelSelectOption } from "../../../types/panel";

export interface IconPickerFieldProps {
  label: string;
  value: string;
  options: PanelSelectOption[];
  onChange: (value: string) => void;
}

/**
 * A trigger button that opens a bottom sheet with a grid of icon buttons —
 * used for pickers whose options are emoji (start reaction, message effect),
 * where a plain dropdown or pill row can't show each choice as its own icon.
 */
export function IconPickerField({ label, value, options, onChange }: IconPickerFieldProps) {
  const [open, setOpen] = useState(false);
  const offValue = options[0]?.value ?? "";
  const current = options.find((option) => option.value === value) ?? options[0];
  const isOff = !current || current.value === offValue;

  return (
    <div>
      <span className="mb-1.5 block text-sm text-muted">{label}</span>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex h-11 w-full items-center justify-between gap-2 rounded-md border border-border bg-surface px-3.5 text-text transition-colors hover:border-primary/50"
      >
        <span className="flex items-center gap-2">
          <span
            className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-lg ${
              isOff ? "bg-surface-2 text-muted" : "bg-primary/10"
            }`}
          >
            {isOff ? "—" : current?.label}
          </span>
          {isOff && current && <span className="text-sm text-muted">{current.label}</span>}
        </span>
        <ChevronDown size={16} className="shrink-0 text-muted" />
      </button>

      <Sheet open={open} onClose={() => setOpen(false)} title={label}>
        <div className="grid max-h-[60vh] grid-cols-6 gap-2 overflow-y-auto sm:grid-cols-8 lg:grid-cols-10">
          {options.map((option) => {
            const active = option.value === value;
            const off = option.value === offValue;
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => {
                  onChange(option.value);
                  setOpen(false);
                }}
                className={`flex h-12 items-center justify-center rounded-lg transition-colors ${
                  active ? "bg-primary text-primary-text" : "bg-surface-2 text-text hover:bg-border"
                } ${off ? "text-xs font-medium" : "text-2xl"}`}
              >
                {option.label}
              </button>
            );
          })}
        </div>
      </Sheet>
    </div>
  );
}
