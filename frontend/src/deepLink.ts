/** `?open=<path>` deep links (built by the bot's `miniapp_deeplink`).
 *
 * Only a small allow-list of in-app paths may be opened this way so a crafted
 * link can't send users anywhere unexpected.
 */
const ALLOWED_PREFIXES = ["/panel/help-buttons", "/bot-reseller"];

/** Normalised allowed path, or null. */
function allowedDeepLink(raw: string | null | undefined): string | null {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//")) return null;
  const pathOnly = raw.split(/[?#]/)[0] ?? "";
  const ok = ALLOWED_PREFIXES.some((prefix) => pathOnly === prefix || pathOnly.startsWith(`${prefix}/`));
  return ok ? raw : null;
}

/** Read `?open=` once and drop it from the URL so a reload doesn't re-trigger it. */
export function takeOpenParam(): string | null {
  try {
    const url = new URL(window.location.href);
    const target = allowedDeepLink(url.searchParams.get("open"));
    if (url.searchParams.has("open")) {
      url.searchParams.delete("open");
      window.history.replaceState(window.history.state, "", `${url.pathname}${url.search}${url.hash}`);
    }
    return target;
  } catch {
    return null;
  }
}
