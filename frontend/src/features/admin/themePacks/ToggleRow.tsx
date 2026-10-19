import { useId } from "react";
import { Switch } from "../../../components/ui";

/** A switch with its label shown next to it (the shared Switch only labels itself for screen readers). */
export function ToggleRow({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  const id = useId();
  return (
    <div className="flex items-center justify-between gap-3">
      <span id={id} className="text-sm text-text">
        {label}
      </span>
      <Switch checked={checked} onChange={onChange} labelledBy={id} />
    </div>
  );
}
