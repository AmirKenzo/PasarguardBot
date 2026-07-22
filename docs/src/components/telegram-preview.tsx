import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

type TelegramPhoneProps = {
  bot?: string;
  title?: string;
  children: ReactNode;
  className?: string;
};

export function TelegramPhone({
  bot = 'PasarguardBot',
  title,
  children,
  className,
}: TelegramPhoneProps) {
  return (
    <div className={cn('not-prose my-6 flex justify-center', className)}>
      <div className="w-full max-w-[360px] overflow-hidden rounded-[2rem] border border-zinc-700/80 bg-[#0e1621] shadow-2xl shadow-black/40 ring-1 ring-white/5">
        <div className="flex items-center gap-3 border-b border-white/5 bg-[#17212b] px-4 py-3">
          <div className="flex size-9 items-center justify-center rounded-full bg-gradient-to-br from-sky-400 to-blue-600 text-sm font-bold text-white">
            P
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-semibold text-white">{bot}</div>
            <div className="text-[11px] text-emerald-400/90">online</div>
          </div>
        </div>

        {title ? (
          <div className="border-b border-white/5 bg-[#0e1621] px-4 py-2 text-center text-[11px] text-zinc-400">
            {title}
          </div>
        ) : null}

        <div className="flex min-h-[420px] flex-col bg-[radial-gradient(ellipse_at_top,_#1a2332_0%,_#0e1621_55%)]">
          {children}
        </div>
      </div>
    </div>
  );
}

export function TgBubble({ children }: { children: ReactNode }) {
  return (
    <div className="flex-1 space-y-3 px-3 py-4">
      <div className="max-w-[85%] rounded-2xl rounded-tr-md bg-[#182533] px-3.5 py-2.5 text-[13px] leading-6 text-zinc-100 shadow-sm">
        {children}
      </div>
    </div>
  );
}

export function TgKeyboard({ children }: { children: ReactNode }) {
  return (
    <div className="mt-auto border-t border-white/5 bg-[#17212b] p-2 pb-3">
      <div className="space-y-1.5">{children}</div>
      <div className="mt-2 flex items-center justify-center gap-6 pt-1 text-zinc-500">
        <span className="text-lg leading-none">☺</span>
        <span className="rounded-full bg-[#0e1621] px-8 py-1.5 text-[11px] text-zinc-400">Message</span>
        <span className="text-lg leading-none">🎤</span>
      </div>
    </div>
  );
}

export function TgRow({ children }: { children: ReactNode }) {
  return <div className="grid grid-flow-col auto-cols-fr gap-1.5">{children}</div>;
}

export function TgBtn({ children }: { children: ReactNode }) {
  return (
    <div className="select-none rounded-xl bg-[#2b5278]/35 px-2 py-2.5 text-center text-[12.5px] font-medium leading-5 text-zinc-50 ring-1 ring-white/5 transition hover:bg-[#2b5278]/55">
      {children}
    </div>
  );
}

export function TelegramGallery({ children }: { children: ReactNode }) {
  return (
    <div className="not-prose my-6 grid gap-6 lg:grid-cols-2 lg:items-start">{children}</div>
  );
}
