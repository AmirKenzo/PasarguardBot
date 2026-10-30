import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { formatNumber } from "../../../lib/format";
import { PageHeader } from "../../../components/layout/PageHeader";
import { Badge, EmptyState } from "../../../components/ui";
import { FormModal } from "../components/FormModal";
import { Toggle as AdminToggle } from "../components/Toggle";

type Tone = "primary" | "success" | "warning" | "danger" | "muted";

export function PageTitle({ title, subtitle }: { title: string; subtitle: string }) {
  return <PageHeader title={title} subtitle={subtitle} />;
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-lg border border-border bg-surface p-4 sm:p-5 ${className}`}>{children}</section>;
}

export function Header({ icon: Icon, title, hint, action }: { icon: LucideIcon; title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div className="flex min-w-0 items-start gap-3">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-primary/12 text-primary">
          <Icon size={17} />
        </span>
        <div className="min-w-0">
          <h2 className="text-sm font-bold text-text">{title}</h2>
          {hint && <p className="mt-0.5 text-xs text-muted">{hint}</p>}
        </div>
      </div>
      {action}
    </div>
  );
}

export function Empty({ icon, title, hint }: { icon: LucideIcon; title: string; hint?: string }) {
  return <EmptyState icon={icon} title={title} description={hint} />;
}

export function Pill({ tone, children, dot = false }: { tone: Tone; children: ReactNode; dot?: boolean }) {
  return (
    <Badge tone={tone}>
      <span className="inline-flex items-center gap-1.5">
        {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" />}
        {children}
      </span>
    </Badge>
  );
}

export function Chips<T extends string | number>({ items, value, onChange }: { items: { value: T; label: ReactNode; count?: number }[]; value: T; onChange: (v: T) => void; id?: string }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => {
        const active = item.value === value;
        return (
          <button
            key={String(item.value)}
            type="button"
            onClick={() => onChange(item.value)}
            className={`inline-flex h-9 items-center gap-1.5 rounded-full px-3.5 text-xs font-bold transition-colors ${active ? "bg-primary text-primary-text" : "bg-surface-2 text-muted hover:text-text"}`}
          >
            {item.label}
            {item.count !== undefined && <span className={`rounded-full px-1.5 text-[10px] ${active ? "bg-white/20" : "bg-surface"}`}>{formatNumber(item.count)}</span>}
          </button>
        );
      })}
    </div>
  );
}

export function Dialog({ open, onClose, title, subtitle, children, wide = false }: { open: boolean; onClose: () => void; icon?: LucideIcon; title: string; subtitle?: string; children: ReactNode; wide?: boolean }) {
  return (
    <FormModal open={open} onClose={onClose} title={title} size={wide ? "xl" : "md"}>
      {subtitle && <p className="-mt-2 mb-3 text-xs text-muted">{subtitle}</p>}
      {children}
    </FormModal>
  );
}

export function Toggle({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label: string }) {
  return <AdminToggle checked={on} onChange={onChange} label={label} />;
}

export function TelegramName({ id, showId = false }: { id: number; showId?: boolean }) {
  return (
    <a href={`tg://user?id=${id}`} className="inline-flex items-center gap-1.5 text-sm font-bold text-text hover:text-primary" dir="ltr">
      {showId ? id : formatNumber(id)}
    </a>
  );
}
