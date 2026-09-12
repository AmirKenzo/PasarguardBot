import { motion } from "framer-motion";
import { Moon, Sun, SunMoon } from "lucide-react";
import { useTheme } from "../../design/ThemeProvider";
import type { ThemeMode } from "../../design/ThemeProvider";

const OPTIONS: { value: ThemeMode; icon: typeof Sun; label: string }[] = [
  { value: "light", icon: Sun, label: "روشن" },
  { value: "auto", icon: SunMoon, label: "خودکار" },
  { value: "dark", icon: Moon, label: "تیره" },
];

export function ThemeToggle() {
  const { mode, setMode } = useTheme();

  return (
    <div className="relative inline-flex items-center gap-0.5 rounded-full border border-border bg-surface-2 p-1">
      {OPTIONS.map((opt) => {
        const active = opt.value === mode;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => setMode(opt.value)}
            aria-label={opt.label}
            aria-pressed={active}
            className="relative flex h-8 w-8 items-center justify-center rounded-full"
          >
            {active && (
              <motion.span
                layoutId="theme-toggle-pill"
                className="absolute inset-0 rounded-full bg-primary shadow-md"
                transition={{ type: "spring", stiffness: 500, damping: 32 }}
              />
            )}
            <opt.icon
              size={15}
              strokeWidth={2.1}
              className={`relative z-10 transition-colors ${active ? "text-primary-text" : "text-muted"}`}
            />
          </button>
        );
      })}
    </div>
  );
}
