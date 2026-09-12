import { forwardRef } from "react";
import type { ButtonHTMLAttributes } from "react";
import { motion } from "framer-motion";
import { Spinner } from "./Spinner";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

type NativeButtonProps = Omit<
  ButtonHTMLAttributes<HTMLButtonElement>,
  "onDrag" | "onDragStart" | "onDragEnd" | "onAnimationStart" | "onAnimationEnd"
>;

export interface ButtonProps extends NativeButtonProps {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  fullWidth?: boolean;
}

const VARIANT_CLASSES: Record<Variant, string> = {
  primary:
    "bg-gradient-to-l from-primary to-primary-strong text-primary-text shadow-md shadow-primary/30 hover:shadow-lg hover:shadow-primary/40",
  secondary: "bg-surface-2 text-text border border-border shadow-sm hover:bg-surface hover:border-primary/30",
  ghost: "bg-transparent text-text hover:bg-surface-2",
  danger: "bg-gradient-to-l from-danger to-danger/80 text-white shadow-md shadow-danger/25 hover:shadow-lg hover:shadow-danger/35",
};

const SIZE_CLASSES: Record<Size, string> = {
  sm: "h-9 px-3.5 text-sm gap-1.5",
  md: "h-11 px-5 text-sm gap-2",
  lg: "h-13 px-7 text-base gap-2",
};

const SHINE_VARIANTS = new Set<Variant>(["primary", "danger"]);

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading = false, fullWidth = false, disabled, className = "", children, ...rest },
  ref
) {
  return (
    <motion.button
      ref={ref}
      whileHover={disabled || loading ? undefined : { y: -1 }}
      whileTap={disabled || loading ? undefined : { scale: 0.96, y: 0 }}
      transition={{ type: "spring", stiffness: 500, damping: 28 }}
      disabled={disabled || loading}
      className={`group relative inline-flex items-center justify-center overflow-hidden rounded-md font-semibold transition-[box-shadow,background-color,border-color] duration-200 disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none ${VARIANT_CLASSES[variant]} ${SIZE_CLASSES[size]} ${fullWidth ? "w-full" : ""} ${className}`}
      {...rest}
    >
      {SHINE_VARIANTS.has(variant) && !disabled && !loading && (
        <span
          aria-hidden="true"
          className="pointer-events-none absolute inset-y-0 -left-1/3 w-1/3 -skew-x-12 bg-white/25 opacity-0 blur-sm transition-all duration-700 group-hover:left-[110%] group-hover:opacity-100"
        />
      )}
      {loading && <Spinner size={16} />}
      <span className="relative z-10 inline-flex items-center gap-2">{children}</span>
    </motion.button>
  );
});
