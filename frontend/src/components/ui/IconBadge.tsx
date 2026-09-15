import type { LucideIcon } from "lucide-react";

type Tone = "primary" | "success" | "warning" | "danger" | "muted" | "accent";
type Size = "sm" | "md" | "lg";

const TONE_CLASSES: Record<Tone, string> = {
  primary: "bg-primary/10 text-primary ring-1 ring-primary/20",
  success: "bg-success/10 text-success ring-1 ring-success/20",
  warning: "bg-warning/10 text-warning ring-1 ring-warning/20",
  danger: "bg-danger/10 text-danger ring-1 ring-danger/20",
  muted: "bg-surface-2 text-muted ring-1 ring-border",
  accent: "bg-accent/10 text-accent ring-1 ring-accent/20",
};

const SIZE_CLASSES: Record<Size, { box: string; icon: number }> = {
  sm: { box: "h-8 w-8 rounded-md", icon: 16 },
  md: { box: "h-10 w-10 rounded-md", icon: 20 },
  lg: { box: "h-12 w-12 rounded-lg", icon: 24 },
};

export interface IconBadgeProps {
  icon: LucideIcon;
  tone?: Tone;
  size?: Size;
  className?: string;
}

export function IconBadge({ icon: Icon, tone = "primary", size = "md", className = "" }: IconBadgeProps) {
  const { box, icon } = SIZE_CLASSES[size];
  return (
    <span className={`inline-flex shrink-0 items-center justify-center ${box} ${TONE_CLASSES[tone]} ${className}`}>
      <Icon size={icon} strokeWidth={1.9} />
    </span>
  );
}
