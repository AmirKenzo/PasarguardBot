import { clsx } from "clsx";
import type { ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [{ text: ["3xs", "2xs", "xs-plus"] }],
    },
  },
});

/** Merges Tailwind classes, resolving conflicts by the last one specified (instead of source order). */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
