import { motion } from "framer-motion";

export interface ProgressRingProps {
  percent: number;
  size?: number;
  strokeWidth?: number;
  tone?: "primary" | "warning" | "danger";
  label?: string;
  sublabel?: string;
}

const TONE_STROKE: Record<NonNullable<ProgressRingProps["tone"]>, string> = {
  primary: "stroke-primary",
  warning: "stroke-warning",
  danger: "stroke-danger",
};

export function ProgressRing({ percent, size = 116, strokeWidth = 10, tone = "primary", label, sublabel }: ProgressRingProps) {
  const clamped = Math.min(100, Math.max(0, percent));
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - clamped / 100);

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} strokeWidth={strokeWidth} className="stroke-surface-2" fill="none" />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={strokeWidth}
          fill="none"
          strokeLinecap="round"
          className={TONE_STROKE[tone]}
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 0.9, ease: "easeOut" }}
        />
      </svg>
      <div className="absolute flex flex-col items-center justify-center text-center">
        <span className="text-lg font-bold text-text">{clamped}%</span>
        {label && <span className="text-[11px] text-muted">{label}</span>}
        {sublabel && <span className="text-[10px] text-muted">{sublabel}</span>}
      </div>
    </div>
  );
}
