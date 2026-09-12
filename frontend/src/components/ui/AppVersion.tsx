export function AppVersion({ className = "" }: { className?: string }) {
  return <span className={`select-none text-[10px] tracking-wide text-muted/70 ${className}`}>نسخه {__APP_VERSION__}</span>;
}
