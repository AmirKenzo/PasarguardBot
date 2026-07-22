import type { ReactNode } from 'react';

type CliPanelProps = {
  title?: string;
  children: ReactNode;
};

/** Terminal-style panel that mirrors pasarguardbot.sh menu UI. */
export function CliPanel({ title, children }: CliPanelProps) {
  return (
    <div className="not-prose my-5 overflow-hidden rounded-xl border border-zinc-800 bg-[#0b1220] shadow-sm">
      {title ? (
        <div className="flex items-center gap-2 border-b border-zinc-800 bg-zinc-900/80 px-4 py-2">
          <span className="size-2 rounded-full bg-red-400/80" />
          <span className="size-2 rounded-full bg-amber-400/80" />
          <span className="size-2 rounded-full bg-emerald-400/80" />
          <span className="ms-2 text-xs font-medium text-cyan-300/90">{title}</span>
        </div>
      ) : null}
      <pre
        className="overflow-x-auto p-4 text-[12.5px] leading-7 text-zinc-200"
        dir="ltr"
        style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace' }}
      >
        {children}
      </pre>
    </div>
  );
}

type CliPromptProps = {
  label: string;
  hint?: string;
  required?: boolean;
};

export function CliPrompt({ label, hint, required }: CliPromptProps) {
  return (
    <div className="not-prose my-3 rounded-xl border bg-fd-card p-4">
      <div className="mb-1 flex flex-wrap items-center gap-2">
        <code className="rounded bg-fd-secondary px-1.5 py-0.5 text-xs" dir="ltr">
          {label}
        </code>
        {required ? (
          <span className="rounded-full bg-red-500/15 px-2 py-0.5 text-[10px] font-semibold text-red-400">
            اجباری
          </span>
        ) : (
          <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold text-emerald-400">
            اختیاری
          </span>
        )}
      </div>
      {hint ? <p className="m-0 text-sm leading-7 text-fd-muted-foreground">{hint}</p> : null}
    </div>
  );
}
