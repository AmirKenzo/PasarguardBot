export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div className={`relative overflow-hidden rounded-md bg-surface-2 ring-1 ring-border/50 ${className}`}>
      <div className="animate-shimmer absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-primary/15 to-transparent" />
    </div>
  );
}

export function SkeletonCard() {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center gap-3">
        <Skeleton className="h-10 w-10 rounded-full" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-3.5 w-2/3" />
          <Skeleton className="h-3 w-1/3" />
        </div>
      </div>
    </div>
  );
}
