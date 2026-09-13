import { useId } from "react";
import { motion } from "framer-motion";

export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
}

export interface SegmentedControlProps<T extends string> {
  options: SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  columns?: number;
}

export function SegmentedControl<T extends string>({ options, value, onChange, columns }: SegmentedControlProps<T>) {
  const layoutId = useId();
  return (
    <div
      className="grid gap-1 rounded-lg border border-border bg-surface/70 p-1 shadow-sm backdrop-blur-md backdrop-saturate-150"
      style={{ gridTemplateColumns: `repeat(${columns || Math.min(options.length, 4)}, minmax(0, 1fr))` }}
    >
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <motion.button
            key={opt.value}
            type="button"
            whileTap={{ scale: 0.96 }}
            onClick={() => onChange(opt.value)}
            className={`relative rounded-md px-3 py-2 text-sm font-medium transition-colors ${
              active ? "text-primary-text" : "text-muted hover:text-text"
            }`}
          >
            {active && (
              <motion.span
                layoutId={`segmented-active-${layoutId}`}
                className="absolute inset-0 rounded-md bg-gradient-to-l from-primary to-primary-strong shadow-sm shadow-primary/30"
                transition={{ type: "spring", stiffness: 500, damping: 32 }}
              />
            )}
            <span className="relative z-10">{opt.label}</span>
          </motion.button>
        );
      })}
    </div>
  );
}
