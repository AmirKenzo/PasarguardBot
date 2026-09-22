import { useCallback, useMemo } from "react";

function getWebApp() {
  return typeof window !== "undefined" ? window.Telegram?.WebApp : undefined;
}

/** Thin wrapper around the Telegram WebApp SDK: haptics, back button, native dialogs. No-ops outside Telegram. */
export function useTelegram() {
  const webApp = getWebApp();

  const haptic = useMemo(
    () => ({
      impact: (style: "light" | "medium" | "heavy" | "rigid" | "soft" = "light") =>
        webApp?.HapticFeedback?.impactOccurred(style),
      notify: (type: "error" | "success" | "warning") => webApp?.HapticFeedback?.notificationOccurred(type),
      select: () => webApp?.HapticFeedback?.selectionChanged(),
    }),
    [webApp]
  );

  const showBackButton = useCallback(
    (onClick: () => void) => {
      const btn = webApp?.BackButton;
      if (!btn) return () => {};
      btn.onClick(onClick);
      btn.show();
      return () => {
        btn.offClick(onClick);
        btn.hide();
      };
    },
    [webApp]
  );

  const openLink = useCallback(
    (url: string) => {
      if (webApp) webApp.openLink(url, { try_instant_view: false });
      else window.open(url, "_blank", "noopener,noreferrer");
    },
    [webApp]
  );

  const openInvoice = useCallback(
    (url: string, callback?: (status: "paid" | "cancelled" | "failed" | "pending") => void) => {
      if (!webApp?.openInvoice) {
        callback?.("failed");
        return;
      }
      webApp.openInvoice(url, callback);
    },
    [webApp]
  );

  // These throw (rather than being undefined) on Telegram clients older than
  // Bot API 8.0, so both the feature check and a try/catch are needed.
  const homeScreenSupported = useCallback(
    () => !!webApp?.isVersionAtLeast?.("8.0") && !!webApp.addToHomeScreen && !!webApp.checkHomeScreenStatus,
    [webApp]
  );

  const addToHomeScreen = useCallback(() => {
    if (!homeScreenSupported()) return;
    try {
      webApp?.addToHomeScreen?.();
    } catch {
      // unsupported on this client — nothing to do
    }
  }, [webApp, homeScreenSupported]);

  const checkHomeScreenStatus = useCallback(
    (cb: (status: "unsupported" | "unknown" | "added" | "missed") => void) => {
      if (!homeScreenSupported()) {
        cb("unsupported");
        return;
      }
      try {
        webApp?.checkHomeScreenStatus?.(cb);
      } catch {
        cb("unsupported");
      }
    },
    [webApp, homeScreenSupported]
  );

  return {
    webApp,
    isTelegram: !!webApp,
    platform: webApp?.platform,
    haptic,
    showBackButton,
    openLink,
    openInvoice,
    addToHomeScreen,
    checkHomeScreenStatus,
  };
}
