import { useCallback, useEffect, useState } from "react";

/**
 * Telegram's embedded webview (notably Desktop) can fail to repaint the page
 * when the viewport size changes (e.g. the user toggles fullscreen), leaving
 * stale layout dimensions with visible dead space around the content.
 *
 * This only nudges the page to recompute layout at whatever size Telegram
 * is already giving it — it must NOT call expand() or request/exit
 * fullscreen itself, since that would override the display mode configured
 * in BotFather (compact vs. default/fullscreen) and the user's own
 * fullscreen toggle. Telegram stays fully in control of sizing; we just
 * make sure our CSS reflows to match.
 */
export function useTelegramViewportFix(): void {
  useEffect(() => {
    const webApp = window.Telegram?.WebApp;
    if (!webApp) return;

    const nudgeReflow = () => {
      window.dispatchEvent(new Event("resize"));
      // Reading layout geometry forces a synchronous recalculation in
      // webviews that otherwise skip repainting after an external resize.
      void document.documentElement.offsetHeight;
    };

    webApp.onEvent("viewportChanged", nudgeReflow);
    webApp.onEvent("fullscreenChanged", nudgeReflow);

    return () => {
      webApp.offEvent("viewportChanged", nudgeReflow);
      webApp.offEvent("fullscreenChanged", nudgeReflow);
    };
  }, []);
}

/**
 * In Fullscreen launch mode, Telegram draws its own floating controls
 * (close/minimize, and on some platforms the status bar background) on top
 * of our content instead of reserving layout space for them. Telegram
 * reports how much space that chrome takes up via `safeAreaInset` (device
 * notch/status bar) and `contentSafeAreaInset` (Telegram's own controls) —
 * without applying these, top-of-page buttons render underneath that chrome
 * and become unclickable. This mirrors both into CSS vars that `.safe-area-pt`
 * (see index.css) turns into padding.
 */
export function useTelegramSafeArea(): void {
  useEffect(() => {
    const webApp = window.Telegram?.WebApp;
    if (!webApp) return;

    const root = document.documentElement.style;
    const applyInsets = () => {
      const safe = webApp.safeAreaInset;
      const content = webApp.contentSafeAreaInset;
      root.setProperty("--tg-safe-area-top", `${safe?.top ?? 0}px`);
      root.setProperty("--tg-safe-area-bottom", `${safe?.bottom ?? 0}px`);
      root.setProperty("--tg-content-safe-area-top", `${content?.top ?? 0}px`);
      root.setProperty("--tg-content-safe-area-bottom", `${content?.bottom ?? 0}px`);
    };

    applyInsets();
    webApp.onEvent("safeAreaChanged", applyInsets);
    webApp.onEvent("contentSafeAreaChanged", applyInsets);

    return () => {
      webApp.offEvent("safeAreaChanged", applyInsets);
      webApp.offEvent("contentSafeAreaChanged", applyInsets);
    };
  }, []);
}

/**
 * Manual fullscreen toggle. BotFather's "Fullscreen" launch mode only
 * applies automatically to the bot's Main Mini App entry point (the
 * persistent menu button) — a web_app button attached to an ordinary
 * message, like the admin panel button, always opens at the platform's
 * default size. Rather than force fullscreen on load, this just exposes the
 * current state and a toggle for an explicit button (see FullscreenToggle).
 */
export function useTelegramFullscreen() {
  const webApp = window.Telegram?.WebApp;
  const supported = typeof webApp?.requestFullscreen === "function";
  const [isFullscreen, setIsFullscreen] = useState(() => !!webApp?.isFullscreen);

  useEffect(() => {
    if (!webApp) return;
    const sync = () => setIsFullscreen(!!webApp.isFullscreen);
    webApp.onEvent("fullscreenChanged", sync);
    return () => webApp.offEvent("fullscreenChanged", sync);
  }, [webApp]);

  const toggle = useCallback(() => {
    if (isFullscreen) webApp?.exitFullscreen?.();
    else webApp?.requestFullscreen?.();
  }, [webApp, isFullscreen]);

  return { isFullscreen, toggle, supported };
}
