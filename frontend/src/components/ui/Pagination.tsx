import { motion } from "framer-motion";
import { ChevronLeft, ChevronRight, MoreHorizontal } from "lucide-react";
import type { ReactNode } from "react";

export interface PaginationProps {
  page: number;
  totalPages: number;
  onChange: (page: number) => void;
}

type PageItem = number | "ellipsis-l" | "ellipsis-r";

function getPageList(current: number, total: number): PageItem[] {
  const delta = 1;
  const left = Math.max(2, current - delta);
  const right = Math.min(total - 1, current + delta);

  const pages: PageItem[] = [1];
  if (left > 2) pages.push("ellipsis-l");
  for (let i = left; i <= right; i++) pages.push(i);
  if (right < total - 1) pages.push("ellipsis-r");
  if (total > 1) pages.push(total);
  return pages;
}

function NavButton({
  onClick,
  disabled,
  label,
  children,
}: {
  onClick: () => void;
  disabled: boolean;
  label: string;
  children: ReactNode;
}) {
  return (
    <motion.button
      onClick={onClick}
      disabled={disabled}
      whileHover={disabled ? undefined : { y: -1 }}
      whileTap={disabled ? undefined : { scale: 0.96 }}
      transition={{ type: "spring", stiffness: 500, damping: 26 }}
      className={`flex h-9 shrink-0 items-center gap-1.5 rounded-full border border-border px-2.5 text-sm font-medium backdrop-blur-md transition-colors sm:px-4 ${
        disabled
          ? "bg-surface/40 text-muted/40"
          : "bg-surface/70 text-text shadow-sm hover:border-primary/40 hover:bg-primary/10 hover:text-primary"
      }`}
      aria-label={label}
    >
      {children}
    </motion.button>
  );
}

export function Pagination({ page, totalPages, onChange }: PaginationProps) {
  if (totalPages <= 1) return null;
  const pages = getPageList(page, totalPages);

  return (
    <div className="flex items-center justify-center gap-1.5 sm:gap-2">
      <NavButton onClick={() => onChange(page - 1)} disabled={page <= 1} label="صفحه قبل">
        <ChevronRight size={15} strokeWidth={2.2} />
        <span className="hidden sm:inline">قبلی</span>
      </NavButton>

      <div className="flex items-center gap-1">
        {pages.map((p, i) =>
          typeof p === "number" ? (
            <motion.button
              key={p}
              onClick={() => onChange(p)}
              whileTap={{ scale: 0.92 }}
              className={`relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-semibold transition-colors ${
                p === page ? "text-primary-text" : "text-muted hover:text-text"
              }`}
              aria-current={p === page ? "page" : undefined}
              aria-label={`صفحه ${p}`}
            >
              {p === page && (
                <motion.span
                  layoutId="pagination-active"
                  className="absolute inset-0 rounded-full bg-gradient-to-l from-primary to-primary-strong shadow-md shadow-primary/30"
                  transition={{ type: "spring", stiffness: 500, damping: 32 }}
                />
              )}
              <span className="relative z-10">{p.toLocaleString("fa-IR")}</span>
            </motion.button>
          ) : (
            <span key={`${p}-${i}`} className="flex h-9 w-5 shrink-0 items-center justify-center text-muted/60 sm:w-6">
              <MoreHorizontal size={16} />
            </span>
          )
        )}
      </div>

      <NavButton onClick={() => onChange(page + 1)} disabled={page >= totalPages} label="صفحه بعد">
        <span className="hidden sm:inline">بعدی</span>
        <ChevronLeft size={15} strokeWidth={2.2} />
      </NavButton>
    </div>
  );
}
