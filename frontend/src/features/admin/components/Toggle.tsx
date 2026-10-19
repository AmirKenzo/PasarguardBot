import { useId } from "react";
import { Switch } from "../../../components/ui";

export interface ToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  hint?: string;
  disabled?: boolean;
}

export function Toggle({ checked, onChange, label, hint, disabled = false }: ToggleProps) {
  const labelId = useId();
  const hintId = useId();
  return (
    <label className={`flex items-start gap-3 py-1.5 ${disabled ? "cursor-not-allowed" : "cursor-pointer"}`}>
      <Switch
        checked={checked}
        onChange={onChange}
        disabled={disabled}
        labelledBy={labelId}
        describedBy={hint ? hintId : undefined}
        className="mt-0.5"
      />
      <span className="text-sm">
        <span id={labelId} className="block text-text">
          {label}
        </span>
        {hint && (
          <span id={hintId} className="mt-0.5 block text-xs text-muted">
            {hint}
          </span>
        )}
      </span>
    </label>
  );
}
