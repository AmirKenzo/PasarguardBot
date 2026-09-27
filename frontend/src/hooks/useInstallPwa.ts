import { useCallback, useEffect, useState } from "react";
import { useTelegram } from "./useTelegram";

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

function isStandalone() {
  if (typeof window === "undefined") return false;
  return window.matchMedia?.("(display-mode: standalone)").matches || (window.navigator as { standalone?: boolean }).standalone === true;
}

/**
 * "Add to home screen" for both surfaces this app runs on:
 *  - Inside Telegram, that's `Telegram.WebApp.addToHomeScreen()` (Bot API 8.0+).
 *  - In a regular browser, it's the standard `beforeinstallprompt` PWA flow.
 */
export function useInstallPwa() {
  const { isTelegram, addToHomeScreen, checkHomeScreenStatus } = useTelegram();
  const [browserPrompt, setBrowserPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [telegramStatus, setTelegramStatus] = useState<"unsupported" | "unknown" | "added" | "missed">("unknown");

  useEffect(() => {
    if (isTelegram) {
      checkHomeScreenStatus(setTelegramStatus);
      return;
    }
    function onPrompt(event: Event) {
      event.preventDefault();
      setBrowserPrompt(event as BeforeInstallPromptEvent);
    }
    window.addEventListener("beforeinstallprompt", onPrompt);
    return () => window.removeEventListener("beforeinstallprompt", onPrompt);
  }, [isTelegram, checkHomeScreenStatus]);

  const install = useCallback(async () => {
    if (isTelegram) {
      addToHomeScreen();
      return;
    }
    if (!browserPrompt) return;
    await browserPrompt.prompt();
    const choice = await browserPrompt.userChoice;
    if (choice.outcome === "accepted") setBrowserPrompt(null);
  }, [isTelegram, addToHomeScreen, browserPrompt]);

  const canInstall = isTelegram
    ? telegramStatus === "unknown" || telegramStatus === "missed"
    : !!browserPrompt && !isStandalone();

  return { canInstall, install };
}
