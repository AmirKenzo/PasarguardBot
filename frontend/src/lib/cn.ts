import { clsx } from "clsx";
import type { ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merges Tailwind classes, resolving conflicts by the last one specified (instead of source order). */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
