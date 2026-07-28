'use client';

import { useState, type ReactNode } from 'react';
import { Check, Copy, ExternalLink } from 'lucide-react';
import { cn } from '@/lib/cn';

type DonateWalletProps = {
  name: string;
  symbol: string;
  network: string;
  address: string;
  note?: string;
  link?: string;
  /** Known icons: trx | usdt | ton | btc | eth | bnb | xrp */
  icon?: 'trx' | 'usdt' | 'ton' | 'btc' | 'eth' | 'bnb' | 'xrp';
};

function CryptoGlyph({ icon, symbol }: { icon?: DonateWalletProps['icon']; symbol: string }) {
  const key = icon ?? symbol.toLowerCase();

  const wrap = (fill: string, children: ReactNode) => (
    <span
      className="inline-flex size-11 shrink-0 items-center justify-center rounded-2xl shadow-sm ring-1 ring-black/5 dark:ring-white/10"
      style={{ background: fill }}
    >
      {children}
    </span>
  );

  if (key === 'trx') {
    return wrap(
      '#FF0013',
      <svg viewBox="0 0 32 32" className="size-6 text-white" aria-hidden>
        <path
          fill="currentColor"
          d="M5.5 6.2h21L16 27.8 5.5 6.2zm3.4 2.2 7.1 14.5 7.1-14.5H8.9zm3.2 2.4h7.8l-3.9 8-3.9-8z"
        />
      </svg>,
    );
  }

  if (key === 'usdt') {
    return wrap(
      '#26A17B',
      <svg viewBox="0 0 32 32" className="size-6 text-white" aria-hidden>
        <path
          fill="currentColor"
          d="M17.5 15.9v2.1c3.4.2 5.9.9 5.9 1.8 0 1-2.9 1.8-6.4 1.8s-6.4-.8-6.4-1.8c0-.9 2.5-1.6 5.8-1.8v-2.1C9.8 16.2 6 17.3 6 18.9c0 2.1 5 3.3 11 3.3s11-1.2 11-3.3c0-1.6-3.8-2.7-10.5-3zm0-2.2v-2H24V9H8v2.7h6.5v2c-5.5.3-9.5 1.5-9.5 3 0 1.8 5.1 3.2 11.5 3.2s11.5-1.4 11.5-3.2c0-1.5-4-2.7-10.5-3z"
        />
      </svg>,
    );
  }

  if (key === 'ton') {
    return wrap(
      '#0098EA',
      <svg viewBox="0 0 32 32" className="size-6 text-white" aria-hidden>
        <path
          fill="currentColor"
          d="M8.2 8.5h15.6c.9 0 1.4.9.9 1.6L17 24.2c-.4.7-1.5.7-1.9 0L7.3 10.1c-.5-.7 0-1.6.9-1.6zm2.4 2.2 5.4 10.1 5.4-10.1H10.6z"
        />
      </svg>,
    );
  }

  if (key === 'btc') {
    return wrap(
      '#F7931A',
      <svg viewBox="0 0 32 32" className="size-6 text-white" aria-hidden>
        <path
          fill="currentColor"
          d="M20.4 14.2c.3-2-1.2-3.1-3.3-3.8l.7-2.7-1.6-.4-.7 2.6c-.4-.1-.9-.2-1.3-.3l.7-2.6-1.6-.4-.7 2.7c-.4-.1-.7-.2-1.1-.3l-2.2-.5-.4 1.7s1.2.3 1.1.3c.6.2.8.5.7.9l-.7 3c0 0 .1 0 .2.1h-.2l-1.1 4.3c-.1.2-.3.5-.7.4 0 0-1.1-.3-1.1-.3l-.8 1.8 2.1.5c.4.1.8.2 1.1.3l-.7 2.7 1.6.4.7-2.7c.4.1.9.2 1.3.3l-.7 2.7 1.6.4.7-2.7c2.9.6 5.1.3 6-2.3.7-2.1 0-3.3-1.5-4.1 1.1-.2 1.9-1 2.1-2.5zm-3.7 5.2c-.5 2.1-4.1.9-5.2.7l.9-3.7c1.2.3 4.9.9 4.3 3zm.5-5.3c-.5 1.9-3.4.9-4.3.7l.8-3.3c1 .2 4 .7 3.5 2.6z"
        />
      </svg>,
    );
  }

  if (key === 'eth') {
    return wrap(
      '#627EEA',
      <svg viewBox="0 0 32 32" className="size-6 text-white" aria-hidden>
        <path fill="currentColor" d="M16 4v9.2l7.8 3.5L16 4z" opacity=".6" />
        <path fill="currentColor" d="M16 4 8.2 16.7 16 13.2V4z" />
        <path fill="currentColor" d="M16 21.9v6.1l7.8-10.8L16 21.9z" opacity=".6" />
        <path fill="currentColor" d="M16 28v-6.1l-7.8-4.7L16 28z" />
        <path fill="currentColor" d="m16 20.6 7.8-4 7.8-4L16 20.6z" opacity=".2" />
        <path fill="currentColor" d="m8.2 16.7 7.8 4 0-7.5-7.8 3.5z" opacity=".6" />
      </svg>,
    );
  }

  if (key === 'bnb') {
    return wrap(
      '#F3BA2F',
      <svg viewBox="0 0 32 32" className="size-6 text-white" aria-hidden>
        <path
          fill="currentColor"
          d="M16 6.2 18.7 9l-5.4 5.4L16 17.1l2.7-2.7 2.7 2.7-5.4 5.4L16 25.8l-8.1-8.1L16 9.5V6.2zm0 0 8.1 8.1-2.7 2.7-5.4-5.4L16 9.5V6.2zM9.5 16.1l2.7-2.7 2.7 2.7-2.7 2.7-2.7-2.7zm9.1 0 2.7-2.7 2.7 2.7-2.7 2.7-2.7-2.7z"
        />
      </svg>,
    );
  }

  if (key === 'xrp') {
    return wrap(
      '#23292F',
      <svg viewBox="0 0 32 32" className="size-6 text-white" aria-hidden>
        <path
          fill="currentColor"
          d="M24.8 7.2h-2.7l-4.6 5.3c-.8.9-2.2.9-3 0L9.9 7.2H7.2l6.3 7.2-6.5 7.4h2.7l4.8-5.5c.8-.9 2.2-.9 3 0l4.8 5.5h2.7l-6.5-7.4 6.3-7.2z"
        />
      </svg>,
    );
  }

  return wrap(
    'var(--color-fd-primary)',
    <span className="text-sm font-bold text-white">{symbol.slice(0, 1)}</span>,
  );
}

export function DonateWallet({
  name,
  symbol,
  network,
  address,
  note,
  link,
  icon,
}: DonateWalletProps) {
  const [copied, setCopied] = useState(false);

  async function copyAddress() {
    try {
      await navigator.clipboard.writeText(address);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      // ignore
    }
  }

  return (
    <div className="not-prose group rounded-2xl border bg-fd-card/80 p-4 transition hover:-translate-y-0.5 hover:border-fd-primary/35 hover:shadow-sm">
      <div className="mb-3 flex items-center gap-3">
        <CryptoGlyph icon={icon} symbol={symbol} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="m-0 text-sm font-semibold text-fd-foreground">{name}</h3>
            <span
              className="rounded-md bg-fd-secondary/70 px-1.5 py-0.5 text-[10px] font-bold tracking-wide text-fd-muted-foreground"
              dir="ltr"
            >
              {symbol}
            </span>
          </div>
          <div className="mt-0.5 text-xs text-fd-muted-foreground" dir="ltr">
            {network}
          </div>
        </div>
      </div>

      {note ? <p className="mb-2 text-xs text-fd-muted-foreground">{note}</p> : null}

      <div
        className="mb-3 break-all rounded-xl border border-dashed bg-fd-secondary/30 px-3 py-2.5 font-mono text-[11px] leading-6 text-fd-foreground"
        dir="ltr"
      >
        {address}
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={copyAddress}
          className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-fd-primary px-3 text-xs font-semibold text-fd-primary-foreground transition hover:opacity-90"
        >
          {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
          {copied ? 'کپی شد' : 'کپی آدرس'}
        </button>
        {link ? (
          <a
            href={link}
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-9 items-center gap-1.5 rounded-lg border bg-fd-background px-3 text-xs font-semibold transition hover:bg-fd-accent"
          >
            <ExternalLink className="size-3.5" />
            لینک
          </a>
        ) : null}
      </div>
    </div>
  );
}

export function DonateGrid({ children }: { children: ReactNode }) {
  return <div className="not-prose my-6 grid gap-4 sm:grid-cols-2">{children}</div>;
}
