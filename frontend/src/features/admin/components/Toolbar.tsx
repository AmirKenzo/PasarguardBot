import type { FormEvent, ReactNode } from "react";

export interface ToolbarProps {
  onSubmit: () => void;
  children: ReactNode;
}

/** Filter bar above a list; submitting applies the filters. */
export function Toolbar({ onSubmit, children }: ToolbarProps) {
  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    onSubmit();
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-surface p-3"
    >
      {children}
    </form>
  );
}
