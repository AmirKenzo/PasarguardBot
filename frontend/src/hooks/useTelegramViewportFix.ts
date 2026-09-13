import { useEffect } from "react";

/**
 * Telegram's embedded webview (notably Desktop) can fail to reflow the page
 * when the user toggles fullscreen or the viewport otherwise changes,
 * leaving the app laid out at its stale (pre-fullscreen) width with visible
 * dead space around it. Re-assert expand() and force a reflow whenever
 * Telegram reports a viewport or fullscreen change.
 */
export function useTelegramViewportFix(): void {
  useEffect(() => {
    const webApp = window.Telegram?.WebApp;
    if (!webApp) return;

    const forceReflow = () => {
      webApp.expand?.();
      window.dispatchEvent(new Event("resize"));
      // Reading layout geometry forces a synchronous recalculation in
      // webviews that otherwise skip repainting after an external resize.
      void document.documentElement.offsetHeight;
    };

    webApp.onEvent("viewportChanged", forceReflow);
    webApp.onEvent("fullscreenChanged", forceReflow);

    return () => {
      webApp.offEvent("viewportChanged", forceReflow);
      webApp.offEvent("fullscreenChanged", forceReflow);
    };
  }, []);
}
