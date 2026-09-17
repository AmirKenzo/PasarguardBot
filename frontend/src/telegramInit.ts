/**
 * Extract Telegram WebApp init data on load, before HashRouter overwrites the hash.
 * Store in sessionStorage for useAuth.
 */
const TG_INIT_STORAGE = "tg_webapp_init_data";

/**
 * Split the launch fragment into the app's own route and Telegram's parameters.
 *
 * Telegram appends its `tgWebApp*` parameters to whatever fragment the URL
 * already carried, so a button pointing at `#/panel` arrives as
 * `#/panel&tgWebAppData=...`. Keeping the leading part is what lets a link open
 * somewhere other than the dashboard.
 */
function splitLaunchHash(hash: string): { route: string; params: string } {
  const match = hash.match(/(^|[&?])tgWebApp/);
  if (!match || match.index === undefined) return { route: hash, params: "" };
  const separator = match[1] ?? "";
  const cut = match.index;
  return {
    route: separator ? hash.slice(0, cut) : "",
    params: hash.slice(separator ? cut + separator.length : cut),
  };
}

function captureTelegramInitData(): void {
  try {
    const hash = window.location.hash.slice(1);
    if (!hash) return;

    const { route, params } = splitLaunchHash(hash);
    const tgWebAppData = new URLSearchParams(params).get("tgWebAppData");
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
      window.location.hash = route.startsWith("/") ? `#${route}` : "#/";
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
