/** Where to send an admin after the WebApp login.
 *
 * Opening /panel without a session bounces through the shared login page,
 * which lands on the user dashboard. Remember what the admin was reaching for
 * so they come back to the panel instead of having to navigate there again.
 *
 * sessionStorage can be unavailable (private mode, blocked site data), so
 * every access is guarded and simply falls back to the default destination.
 */
const KEY = "panel_redirect";

export function rememberPanelRedirect(path: string): void {
  try {
    sessionStorage.setItem(KEY, path);
  } catch {
    // Not being able to remember only costs one extra navigation.
  }
}

export function peekPanelRedirect(): string | null {
  try {
    return sessionStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function clearPanelRedirect(): void {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    // Nothing to clean up if storage is unavailable.
  }
}
