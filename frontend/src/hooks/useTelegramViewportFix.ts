import { useEffect } from "react";

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
