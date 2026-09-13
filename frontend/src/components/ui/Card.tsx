import type { HTMLAttributes } from "react";

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  interactive?: boolean;
}

export function Card({ className = "", interactive = false, ...rest }: CardProps) {
  return (
    <div
      className={`overflow-hidden rounded-lg border border-border bg-surface/75 shadow-sm backdrop-blur-md backdrop-saturate-150 ${
        interactive
          ? "transition-[transform,box-shadow,border-color,background-color] duration-200 hover:-translate-y-0.5 hover:border-primary/30 hover:bg-surface/90 hover:shadow-md active:translate-y-0 active:shadow-sm"
          : ""
      } ${className}`}
      {...rest}
    />
  );
}
