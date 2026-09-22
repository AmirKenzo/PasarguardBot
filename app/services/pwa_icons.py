"""Admin-uploaded PWA icon storage.

The admin uploads one image; we convert it to the fixed set of PNG sizes a
web app manifest needs and store them on local disk (outside ``frontend/``
so they survive a frontend rebuild/redeploy). Falls back to the bundled
placeholder icons shipped in the frontend build when nothing was uploaded yet.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

ICONS_DIR = _PROJECT_ROOT / "data" / "pwa_icons"
FALLBACK_ICONS_DIR = _PROJECT_ROOT / "frontend" / "dist" / "icons"

# (filename, size, maskable) — maskable icons get extra safe-zone padding.
ICON_SPECS: tuple[tuple[str, int, bool], ...] = (
    ("icon-192.png", 192, False),
    ("icon-512.png", 512, False),
    ("icon-maskable-192.png", 192, True),
    ("icon-maskable-512.png", 512, True),
)

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def icon_filenames() -> tuple[str, ...]:
    return tuple(name for name, _, _ in ICON_SPECS)


def has_custom_icon() -> bool:
    return (ICONS_DIR / ICON_SPECS[0][0]).exists()


def resolve_icon_path(filename: str) -> Path | None:
    """Path to serve for ``filename``: the uploaded one, else the bundled default."""
    if filename not in icon_filenames():
        return None
    custom = ICONS_DIR / filename
    if custom.exists():
        return custom
    fallback = FALLBACK_ICONS_DIR / filename
    return fallback if fallback.exists() else None


def _render(source: Image.Image, size: int, maskable: bool) -> Image.Image:
    """Fit the source image into a square canvas, padded for maskable safe-zone."""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    target = int(size * 0.7) if maskable else size
    fitted = source.copy()
    fitted.thumbnail((target, target), Image.LANCZOS)
    offset = ((size - fitted.width) // 2, (size - fitted.height) // 2)
    canvas.paste(fitted, offset, fitted if fitted.mode == "RGBA" else None)
    return canvas


def save_icon(raw: bytes) -> None:
    """Validate ``raw`` as an image and (re)generate every icon size from it."""
    with Image.open(BytesIO(raw)) as img:
        img = img.convert("RGBA")
        ICONS_DIR.mkdir(parents=True, exist_ok=True)
        for filename, size, maskable in ICON_SPECS:
            rendered = _render(img, size, maskable)
            tmp_path = ICONS_DIR / f".{filename}.tmp"
            rendered.save(tmp_path, format="PNG")
            tmp_path.replace(ICONS_DIR / filename)
