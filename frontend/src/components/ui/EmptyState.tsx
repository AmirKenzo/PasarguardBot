import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { Inbox } from "lucide-react";
import { IconBadge } from "./IconBadge";

export interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState({ icon: Icon = Inbox, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border px-6 py-12 text-center">
      <IconBadge icon={Icon} tone="muted" size="lg" className="h-14 w-14" />
      <div>
        <p className="font-medium text-text">{title}</p>
        {description && <p className="mt-1 text-sm text-muted">{description}</p>}
      </div>
      {action}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-danger/25 bg-danger/5 px-6 py-10 text-center">
      <p className="text-sm text-danger">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="text-sm font-medium text-primary hover:underline">
          تلاش دوباره
        </button>
      )}
    </div>
  );
}
