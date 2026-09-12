import { motion } from "framer-motion";
import { ChevronLeft, ChevronRight } from "lucide-react";

export interface PaginationProps {
  page: number;
  totalPages: number;
  onChange: (page: number) => void;
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
  children: React.ReactNode;
}) {
  return (
    <motion.button
      onClick={onClick}
      disabled={disabled}
      whileHover={disabled ? undefined : { y: -1, scale: 1.04 }}
      whileTap={disabled ? undefined : { scale: 0.92 }}
      transition={{ type: "spring", stiffness: 500, damping: 26 }}
      className={`flex h-10 w-10 items-center justify-center rounded-full border transition-colors ${
        disabled
          ? "border-border text-muted/40"
          : "border-border bg-surface text-text shadow-sm hover:border-primary/40 hover:bg-primary/10 hover:text-primary"
      }`}
      aria-label={label}
    >
      {children}
    </motion.button>
  );
}

export function Pagination({ page, totalPages, onChange }: PaginationProps) {
  if (totalPages <= 1) return null;
  return (
    <div className="flex items-center justify-center gap-3">
      <NavButton onClick={() => onChange(page - 1)} disabled={page <= 1} label="صفحه قبل">
        <ChevronRight size={18} strokeWidth={2.2} />
      </NavButton>

      <div className="flex items-center gap-1.5 rounded-full border border-border bg-surface-2 px-4 py-2 text-sm font-medium">
        <span className="text-primary">{page}</span>
        <span className="text-muted">/</span>
        <span className="text-muted">{totalPages}</span>
      </div>

      <NavButton onClick={() => onChange(page + 1)} disabled={page >= totalPages} label="صفحه بعد">
        <ChevronLeft size={18} strokeWidth={2.2} />
      </NavButton>
    </div>
  );
}
