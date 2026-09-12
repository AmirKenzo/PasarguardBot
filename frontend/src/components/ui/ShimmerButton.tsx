import { forwardRef } from "react";
import type { ButtonHTMLAttributes, CSSProperties } from "react";
import { cn } from "../../lib/cn";

export interface ShimmerButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  shimmerColor?: string;
  shimmerSize?: string;
  borderRadius?: string;
  shimmerDuration?: string;
  background?: string;
}

/** Magic UI's shimmer button — a rotating light streak behind a solid pill, adapted to this app's tokens. */
export const ShimmerButton = forwardRef<HTMLButtonElement, ShimmerButtonProps>(function ShimmerButton(
  {
    shimmerColor = "#ffffff",
    shimmerSize = "0.08em",
    shimmerDuration = "2.5s",
    borderRadius = "999px",
    background = "linear-gradient(to left, rgb(var(--c-primary-strong-rgb)), rgb(var(--c-primary-rgb)))",
    className = "",
    children,
    ...rest
  },
  ref
) {
  return (
    <button
      ref={ref}
      style={
        {
          "--spread": "90deg",
          "--shimmer-color": shimmerColor,
          "--radius": borderRadius,
          "--speed": shimmerDuration,
          "--cut": shimmerSize,
          "--bg": background,
        } as CSSProperties
      }
      className={cn(
        "group relative z-0 flex cursor-pointer items-center justify-center gap-2 overflow-hidden whitespace-nowrap px-6 py-3 text-sm font-semibold text-primary-text [background:var(--bg)] [border-radius:var(--radius)]",
        "transform-gpu shadow-md shadow-primary/25 transition-[transform,box-shadow] duration-300 ease-in-out hover:shadow-lg hover:shadow-primary/35 active:translate-y-px",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...rest}
    >
      <div className="absolute inset-0 -z-30 overflow-visible blur-[2px] [container-type:size]">
        <div className="absolute inset-0 h-[100cqh] animate-shimmer-slide [aspect-ratio:1] [border-radius:0]">
          <div className="absolute -inset-full w-auto rotate-0 animate-spin-around [background:conic-gradient(from_calc(270deg-(var(--spread)*0.5)),transparent_0,var(--shimmer-color)_var(--spread),transparent_var(--spread))]" />
        </div>
      </div>

      {children}

      <div className="absolute inset-0 size-full rounded-[inherit] shadow-[inset_0_-8px_10px_#ffffff1f] transition-shadow duration-300 ease-in-out group-hover:shadow-[inset_0_-6px_10px_#ffffff3f] group-active:shadow-[inset_0_-10px_10px_#ffffff3f]" />

      <div className="absolute -z-20 [background:var(--bg)] [border-radius:var(--radius)] [inset:var(--cut)]" />
    </button>
  );
});
