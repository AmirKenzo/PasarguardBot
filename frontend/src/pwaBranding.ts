/**
 * Applies the admin-configured app name/icon to the live page: the browser
 * tab title and favicon. Browsers cache favicons very aggressively by URL, so
 * a changed icon needs a new URL (not just new bytes at the same path) to
 * ever show up — the manifest's icon `src` already carries a `?v=` that bumps
 * on every upload, so reusing it here is what makes the favicon actually update.
 *
 * Fetched from `/api/webapp/...` (not the bare `/webapp/...` the SPA itself is
 * served from): a reverse proxy in front of this app commonly serves `/webapp/`
 * as static files and only forwards `/api/*` to the backend, so anything that
 * must reach the FastAPI app dynamically has to go through `/api/webapp/...` —
 * the same reasoning the `/api/webapp/assets` mount already exists for.
 */
const MANIFEST_URL = "/api/webapp/manifest.webmanifest";

export async function applyPwaBranding(): Promise<void> {
  try {
    const res = await fetch(MANIFEST_URL, { cache: "no-store" });
    if (!res.ok) return;
    const manifest = (await res.json()) as {
      name?: string;
      short_name?: string;
      icons?: { src: string; purpose?: string; sizes?: string }[];
    };

    if (manifest.name) document.title = manifest.name;

    const icon = manifest.icons?.find((item) => item.purpose === "any" && item.sizes === "192x192") || manifest.icons?.[0];
    if (icon?.src) {
      const href = new URL(icon.src, `${window.location.origin}${MANIFEST_URL}`).toString();
      for (const rel of ["icon", "apple-touch-icon"]) {
        let link = document.head.querySelector<HTMLLinkElement>(`link[rel="${rel}"]`);
        if (!link) {
          link = document.createElement("link");
          link.rel = rel;
          document.head.appendChild(link);
        }
        link.href = href;
      }
    }
  } catch {
    // Keep the build-time defaults from index.html if this fails.
  }
}
