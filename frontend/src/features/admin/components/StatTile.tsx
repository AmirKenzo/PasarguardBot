import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { Card, IconBadge } from "../../../components/ui";

type Tone = "default" | "primary" | "success" | "warning" | "danger";

const VALUE_CLASSES: Record<Tone, string> = {
  default: "text-text",
  primary: "text-primary",
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
};

const BADGE_TONES: Record<Tone, "primary" | "success" | "warning" | "danger" | "muted"> = {
  default: "muted",
  primary: "primary",
  success: "success",
  warning: "warning",
  danger: "danger",
};

export interface StatTileProps {
  label: string;
  value: ReactNode;
  /** Exact value shown as a tooltip when `value` is an abbreviated form. */
  exactValue?: string;
  hint?: ReactNode;
  icon?: LucideIcon;
  tone?: Tone;
  /** Tighter padding/type for grids with many tiles on narrow screens. */
  dense?: boolean;
}

export function StatTile({ label, value, exactValue, hint, icon, tone = "default", dense = false }: StatTileProps) {
  return (
    <Card className={dense ? "p-3" : "p-4"}>
      <div className="flex items-start gap-2.5">
        {icon && <IconBadge icon={icon} tone={BADGE_TONES[tone]} size="sm" />}
        <div className="min-w-0 flex-1">
          <p className="truncate text-xs text-muted">{label}</p>
          <p
            title={exactValue}
            className={`mt-1 truncate font-bold ${dense ? "text-sm" : "text-lg"} ${VALUE_CLASSES[tone]}`}
          >
            {value}
          </p>
          {hint && <p className="mt-0.5 truncate text-xs text-muted">{hint}</p>}
        </div>
      </div>
    </Card>
  );
}
