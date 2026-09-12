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
  return (
    <div
      className="grid gap-2"
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
            className={`rounded-md border px-3 py-2.5 text-sm font-medium transition-colors ${
              active
                ? "border-primary bg-primary/10 text-primary"
                : "border-border bg-surface text-text hover:bg-surface-2"
            }`}
          >
            {opt.label}
          </motion.button>
        );
      })}
    </div>
  );
}
