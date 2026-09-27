import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";

export interface TabItem {
  value: string;
  label: string;
  icon?: LucideIcon;
}

export interface TabsProps {
  items: TabItem[];
  value: string;
  onChange: (value: string) => void;
}

export function Tabs({ items, value, onChange }: TabsProps) {
  return (
    <div className="no-scrollbar -mx-4 flex gap-1 overflow-x-auto scroll-smooth rounded-xl bg-surface-2 p-1 md:mx-0">
      {items.map((item) => {
        const active = item.value === value;
        const Icon = item.icon;
        return (
          <button
            key={item.value}
            onClick={() => onChange(item.value)}
            className={`relative flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg px-3 py-1.5 text-xs font-medium transition-colors first:ms-3 last:me-3 sm:text-sm md:first:ms-0 md:last:me-0 ${
              active ? "text-primary" : "text-muted hover:text-text"
            }`}
          >
            {active && (
              <motion.span
                layoutId="tabs-pill"
                className="absolute inset-0 rounded-lg bg-primary/15 ring-1 ring-primary/25"
                transition={{ type: "spring", stiffness: 400, damping: 32 }}
              />
            )}
            {Icon && <Icon size={14} className="relative z-10 shrink-0" />}
            <span className="relative z-10">{item.label}</span>
          </button>
        );
      })}
    </div>
  );
}
