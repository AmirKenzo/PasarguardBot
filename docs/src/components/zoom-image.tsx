'use client';

import { useCallback, useEffect, useId, useState, type KeyboardEvent } from 'react';
import { createPortal } from 'react-dom';
import { Expand, X } from 'lucide-react';
import { cn } from '@/lib/cn';

type StaticImageLike = { src: string };

type ZoomImageProps = {
  src: string | StaticImageLike;
  alt?: string;
  className?: string;
};

function resolveSrc(src: string | StaticImageLike): string {
  return typeof src === 'string' ? src : src.src;
}

function withBasePath(src: string): string {
  if (src.startsWith('http://') || src.startsWith('https://') || src.startsWith('data:')) {
    return src;
  }
  const base = process.env.NEXT_PUBLIC_BASE_PATH || '';
  if (!base) return src;
  return src.startsWith('/') ? `${base}${src}` : `${base}/${src}`;
}

export function ZoomImage({ src, alt = '', className }: ZoomImageProps) {
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const titleId = useId();
  const srcUrl = withBasePath(resolveSrc(src));

  useEffect(() => {
    setMounted(true);
  }, []);

  const close = useCallback(() => setOpen(false), []);
  const openPreview = useCallback(() => setOpen(true), []);

  const onTriggerKeyDown = useCallback(
    (event: KeyboardEvent<HTMLButtonElement>) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        openPreview();
      }
    },
    [openPreview],
  );

  useEffect(() => {
    if (!open) return;

    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') close();
    };

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', onKey);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', onKey);
    };
  }, [open, close]);

  if (!srcUrl) return null;

  return (
    <>
      <figure className="not-prose my-5">
        <button
          type="button"
          onClick={openPreview}
          onKeyDown={onTriggerKeyDown}
          className={cn(
            'group relative block w-full cursor-zoom-in overflow-hidden rounded-xl border bg-fd-card text-start',
            'transition hover:border-fd-primary/50 hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-fd-primary',
          )}
          aria-label={alt ? `بزرگ‌نمایی: ${alt}` : 'بزرگ‌نمایی تصویر'}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={srcUrl}
            alt={alt}
            className={cn('m-0 h-auto max-h-[28rem] w-full object-contain bg-black/5 dark:bg-white/5', className)}
          />
          <span className="pointer-events-none absolute end-3 top-3 inline-flex items-center gap-1.5 rounded-lg border bg-fd-background/90 px-2 py-1 text-xs text-fd-muted-foreground opacity-90 shadow-sm backdrop-blur-sm transition group-hover:opacity-100">
            <Expand className="size-3.5" aria-hidden />
            کلیک برای بزرگ‌نمایی
          </span>
        </button>
        {alt ? <figcaption className="mt-2 text-center text-sm text-fd-muted-foreground">{alt}</figcaption> : null}
      </figure>

      {mounted && open
        ? createPortal(
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby={titleId}
              className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-8"
            >
              <button
                type="button"
                className="absolute inset-0 bg-black/75 backdrop-blur-sm"
                aria-label="بستن"
                onClick={close}
              />
              <div className="relative z-10 flex max-h-full w-full max-w-5xl flex-col gap-3">
                <div className="flex items-center justify-between gap-3 text-white">
                  <p id={titleId} className="truncate text-sm text-white/85">
                    {alt || 'پیش‌نمایش تصویر'}
                  </p>
                  <button
                    type="button"
                    onClick={close}
                    className="inline-flex size-9 shrink-0 items-center justify-center rounded-full border border-white/20 bg-white/10 text-white transition hover:bg-white/20"
                    aria-label="بستن"
                  >
                    <X className="size-4" />
                  </button>
                </div>
                <div className="overflow-auto rounded-2xl border border-white/10 bg-black/40 p-2 shadow-2xl">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={srcUrl}
                    alt={alt}
                    className="mx-auto max-h-[min(85vh,900px)] w-auto max-w-full object-contain"
                  />
                </div>
                <p className="text-center text-xs text-white/60">Esc یا کلیک بیرون از تصویر برای بستن</p>
              </div>
            </div>,
            document.body,
          )
        : null}
    </>
  );
}
