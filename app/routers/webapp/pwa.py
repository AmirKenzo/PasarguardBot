"""Public PWA endpoints: the manifest and icon files, built from admin settings.

Kept dynamic (rather than the static file Vite would otherwise bake in) so an
admin can change the app name/description/icon from the panel without a
frontend rebuild.
"""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse, Response

from app.db.crud.settings import SettingsManager
from app.services.pwa_icons import icon_filenames, resolve_icon_path
from config import WEBAPP_URL

router = APIRouter()

_THEME_COLOR = "#2563eb"
_BACKGROUND_COLOR = "#f4f5f9"


def _webapp_scope() -> str:
    """The path users can actually reach this app through.

    Not always ``/webapp/``: a reverse proxy may only forward ``/api/*`` to
    this backend, in which case the real, working entry point is whatever
    ``WEBAPP_URL`` (already used to open the Telegram Mini App) points at.
    """
    path = urlparse(WEBAPP_URL).path or "/webapp"
    return path if path.endswith("/") else f"{path}/"


@router.get("/webapp/manifest.webmanifest")
async def webapp_manifest() -> Response:
    setting = await SettingsManager().get_settings()
    app_name = (getattr(setting, "pwa_app_name", None) if setting else None) or "PasarguardBot WebApp"
    short_name = (getattr(setting, "pwa_short_name", None) if setting else None) or "PasarguardBot"
    description = (getattr(setting, "pwa_description", None) if setting else None) or ""
    version = int(getattr(setting, "pwa_icon_updated_at", 0) or 0) if setting else 0
    scope = _webapp_scope()

    manifest = {
        "id": scope,
        "name": app_name,
        "short_name": short_name,
        "description": description,
        "start_url": scope,
        "scope": scope,
        "display": "standalone",
        "background_color": _BACKGROUND_COLOR,
        "theme_color": _THEME_COLOR,
        "lang": "fa",
        "dir": "rtl",
        "icons": [
            {"src": f"icons/icon-192.png?v={version}", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": f"icons/icon-512.png?v={version}", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {
                "src": f"icons/icon-maskable-192.png?v={version}",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "maskable",
            },
            {
                "src": f"icons/icon-maskable-512.png?v={version}",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable",
            },
        ],
    }
    return JSONResponse(manifest, media_type="application/manifest+json")


@router.get("/webapp/icons/{filename}")
async def webapp_icon(filename: str) -> Response:
    if filename not in icon_filenames():
        return Response(status_code=404)
    path = resolve_icon_path(filename)
    if path is None:
        return Response(status_code=404)
    # Content is versioned via the manifest's ?v= query string, so a long
    # max-age is safe: a changed icon gets a new URL, not a stale cache hit.
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "public, max-age=31536000"})
