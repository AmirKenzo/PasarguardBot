/**
 * Extract Telegram WebApp init data on load, before HashRouter overwrites the hash.
 * Store in sessionStorage for useAuth.
 */
const TG_INIT_STORAGE = "tg_webapp_init_data";

function captureTelegramInitData(): void {
  try {
    const hash = window.location.hash.slice(1);
    if (!hash) return;

    const params = new URLSearchParams(hash);
    const tgWebAppData = params.get("tgWebAppData");
    if (tgWebAppData) {
      let initData = decodeURIComponent(tgWebAppData);
      if (!initData.includes("=") || !initData.includes("&")) {
        try {
          initData = atob(tgWebAppData.replace(/-/g, "+").replace(/_/g, "/"));
        } catch {
          initData = decodeURIComponent(tgWebAppData);
        }
      }
      sessionStorage.setItem(TG_INIT_STORAGE, initData);
      window.location.hash = "#/";
    }
  } catch {
    // ignore
  }
}

function getStoredInitData(): string | null {
  try {
    const data = sessionStorage.getItem(TG_INIT_STORAGE);
    if (data) {
      sessionStorage.removeItem(TG_INIT_STORAGE);
      return data;
    }
  } catch {
    // ignore
  }
  return null;
}

export { getStoredInitData, captureTelegramInitData };
