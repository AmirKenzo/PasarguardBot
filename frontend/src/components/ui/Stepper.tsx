import { motion } from "framer-motion";
import { Check } from "lucide-react";

export function Stepper({ steps, current }: { steps: string[]; current: number }) {
  return (
    <div className="flex items-center gap-1.5">
      {steps.map((label, idx) => {
        const done = idx < current;
        const active = idx === current;
        return (
          <div key={label} className="flex flex-1 items-center gap-1.5">
            <div
              className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold transition-colors ${
                done
                  ? "bg-primary text-primary-text"
                  : active
                    ? "border-2 border-primary text-primary"
                    : "border border-border text-muted"
              }`}
            >
              {done ? <Check size={14} /> : idx + 1}
            </div>
            {idx < steps.length - 1 && (
              <div className="h-0.5 flex-1 overflow-hidden rounded-full bg-surface-2">
                <motion.div
                  className="h-full bg-primary"
                  initial={false}
                  animate={{ width: done ? "100%" : "0%" }}
                  transition={{ duration: 0.3 }}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
