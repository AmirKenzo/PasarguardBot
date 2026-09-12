import { motion } from "framer-motion";

export interface TabItem {
  value: string;
  label: string;
}

export interface TabsProps {
  items: TabItem[];
  value: string;
  onChange: (value: string) => void;
}

export function Tabs({ items, value, onChange }: TabsProps) {
  return (
    <div className="flex gap-1 rounded-md bg-surface-2 p-1">
      {items.map((item) => {
        const active = item.value === value;
        return (
          <button
            key={item.value}
            onClick={() => onChange(item.value)}
            className={`relative flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
              active ? "text-primary-text" : "text-muted hover:text-text"
            }`}
          >
            {active && (
              <motion.span
                layoutId="tabs-pill"
                className="absolute inset-0 rounded-md bg-primary shadow-sm"
                transition={{ type: "spring", stiffness: 400, damping: 32 }}
              />
            )}
            <span className="relative z-10">{item.label}</span>
          </button>
        );
      })}
    </div>
  );
}
