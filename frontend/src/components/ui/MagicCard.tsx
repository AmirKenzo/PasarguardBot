import { useCallback, useRef } from "react";
import type { HTMLAttributes, MouseEvent as ReactMouseEvent, ReactNode } from "react";
import { motion, useMotionTemplate, useMotionValue } from "framer-motion";
import { cn } from "../../lib/cn";

export interface MagicCardProps extends Omit<HTMLAttributes<HTMLDivElement>, "children"> {
  children?: ReactNode;
  gradientSize?: number;
  gradientFrom?: string;
  gradientTo?: string;
}

/**
 * Magic UI's spotlight card, adapted to this app's tokens. The gradient tracks the pointer
 * on hover — a desktop-only enhancement, since touch devices don't fire mousemove; on mobile
 * it just renders as a plain bordered card.
 */
export function MagicCard({
  children,
  className = "",
  gradientSize = 200,
  gradientFrom = "rgb(var(--c-primary-rgb) / 0.4)",
  gradientTo = "rgb(var(--c-accent-rgb) / 0.25)",
  ...rest
}: MagicCardProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const mouseX = useMotionValue(-gradientSize);
  const mouseY = useMotionValue(-gradientSize);

  const handleMouseMove = useCallback(
    (e: ReactMouseEvent<HTMLDivElement>) => {
      const rect = cardRef.current?.getBoundingClientRect();
      if (!rect) return;
      mouseX.set(e.clientX - rect.left);
      mouseY.set(e.clientY - rect.top);
    },
    [mouseX, mouseY]
  );

  const handleMouseLeave = useCallback(() => {
    mouseX.set(-gradientSize);
    mouseY.set(-gradientSize);
  }, [mouseX, mouseY, gradientSize]);

  const background = useMotionTemplate`radial-gradient(${gradientSize}px circle at ${mouseX}px ${mouseY}px, ${gradientFrom}, ${gradientTo}, transparent 100%)`;

  return (
    <div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      className={cn("group relative overflow-hidden rounded-lg border border-border bg-surface shadow-sm", className)}
      {...rest}
    >
      <motion.div
        className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        style={{ background }}
      />
      <div className="relative z-10">{children}</div>
    </div>
  );
}
