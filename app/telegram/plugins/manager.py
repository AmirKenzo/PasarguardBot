"""Discovers and loads the bot's Telegram modules.

A module is ``app/telegram/{admin,user,business}/<name>.py`` or ``.../<name>/module.py``::

    MODULE_NAME = "user.games"  # default: "<dir>.<name>"
    MODULE_ENABLED = True  # False, or listed in DISABLED_TELEGRAM_MODULES, skips it
    MODULE_ORDER = 1000  # load order, and therefore handler priority; lower first
    MODULE_REQUIRED = False  # the bot refuses to start if a required module fails
    MODULE_DESCRIPTION = ""
    MODULE_VERSION = ""


    def setup(kenzo: PluginContext) -> None: ...  # may be async; ``register`` is also accepted

A module without ``setup``/``register`` registers its handlers on import (``@Kenzo.on``).
An optional module that fails is logged and skipped; the rest of the bot keeps running.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import os
import traceback
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from telethon import TelegramClient

from app import Kenzo
from app.logger import LogTag, get_logger
from app.telegram.plugins.context import PluginContext

logger = get_logger(__name__)

TELEGRAM_ROOT = Path(__file__).resolve().parent.parent
APP_ROOT = TELEGRAM_ROOT.parent
SCANNED_DIRS = ("admin", "user", "business")
METADATA_KEYS = frozenset(
    {"MODULE_NAME", "MODULE_ENABLED", "MODULE_ORDER", "MODULE_REQUIRED", "MODULE_DESCRIPTION", "MODULE_VERSION"}
)

type ModuleStatus = Literal["loaded", "failed"]


class RequiredModuleError(RuntimeError):
    """A required module failed to load."""


@dataclass(frozen=True)
class ModuleSpec:
    name: str
    import_name: str
    path: Path
    order: int = 1000
    required: bool = False
    description: str = ""
    version: str = ""


@dataclass(frozen=True)
class LoadedModule:
    spec: ModuleSpec
    status: ModuleStatus
    handlers: int = 0
    jobs: int = 0
    legacy: bool = False
    error: str | None = None


def _disabled_names() -> frozenset[str]:
    raw = os.getenv("DISABLED_TELEGRAM_MODULES", "")
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def _read_metadata(path: Path) -> dict[str, object]:
    """``MODULE_*`` constants, read without importing so disabled modules never run."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError) as exc:
        logger.warning("%s Could not read module metadata from %s: %s", LogTag.TELEGRAM, path, exc)
        return {}
    metadata: dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in METADATA_KEYS:
                try:
                    metadata[target.id] = ast.literal_eval(node.value)
                except ValueError, SyntaxError:
                    continue
    return metadata


def _default_name(path: Path) -> str | None:
    parts = path.relative_to(TELEGRAM_ROOT).parts
    if path.name == "module.py":
        return f"{parts[0]}.{parts[1]}" if len(parts) == 3 else None
    if path.stem.endswith("_legacy"):
        stem = path.stem.removesuffix("_legacy")
        if (path.with_name(stem) / "module.py").is_file():
            return None
        return ".".join((*parts[:-1], stem))
    return f"{parts[0]}.{path.stem}" if len(parts) == 2 else None


def _candidate_paths() -> Iterator[Path]:
    for dirname in SCANNED_DIRS:
        root = TELEGRAM_ROOT / dirname
        if root.is_dir():
            yield from sorted(root.glob("*.py"))
            yield from sorted(root.glob("*/module.py"))


def _is_skipped(path: Path) -> bool:
    parts = path.relative_to(TELEGRAM_ROOT).parts
    return path.name == "__init__.py" or path.name.startswith("!") or any(p.startswith("_") for p in parts)


def discover_modules() -> list[ModuleSpec]:
    """Enabled modules sorted by ``(MODULE_ORDER, MODULE_NAME)``."""
    disabled = _disabled_names()
    specs: dict[str, ModuleSpec] = {}
    for path in _candidate_paths():
        if _is_skipped(path) or (default_name := _default_name(path)) is None:
            continue
        meta = _read_metadata(path)
        name = str(meta.get("MODULE_NAME") or default_name)
        if name in specs:
            logger.warning("%s Duplicate module %s skipped: %s", LogTag.PLUGIN, name, path)
            continue
        if name in disabled or not meta.get("MODULE_ENABLED", True):
            logger.info("%s Module disabled: %s", LogTag.TELEGRAM, name)
            continue
        specs[name] = ModuleSpec(
            name=name,
            import_name=".".join(("app", *path.relative_to(APP_ROOT).with_suffix("").parts)),
            path=path,
            order=int(meta.get("MODULE_ORDER", 1000)),
            required=bool(meta.get("MODULE_REQUIRED", False)),
            description=str(meta.get("MODULE_DESCRIPTION", "")),
            version=str(meta.get("MODULE_VERSION", "")),
        )
    return sorted(specs.values(), key=lambda spec: (spec.order, spec.name))


class PluginManager:
    def __init__(self, client: TelegramClient) -> None:
        self.client = client
        self._modules: dict[str, LoadedModule] = {}

    @property
    def modules(self) -> tuple[LoadedModule, ...]:
        return tuple(self._modules.values())

    async def load(self, spec: ModuleSpec) -> LoadedModule:
        kenzo = PluginContext(spec.name, self.client)
        try:
            module = importlib.import_module(spec.import_name)
            entry = getattr(module, "setup", None) or getattr(module, "register", None)
            if callable(entry):
                result = entry(kenzo)
                if inspect.isawaitable(result):
                    await result
        except Exception as exc:
            loaded = LoadedModule(spec, "failed", error=f"{type(exc).__name__}: {exc}")
            self._modules[spec.name] = loaded
            logger.error(
                "%s ✗ %s failed to load: %s\n%s",
                LogTag.PLUGIN,
                spec.name,
                loaded.error,
                "".join(traceback.format_exception(exc)),
            )
            if spec.required:
                raise RequiredModuleError(f"Required module {spec.name} failed to load") from exc
            return loaded

        loaded = LoadedModule(spec, "loaded", kenzo.handler_count, len(kenzo.job_ids), legacy=not callable(entry))
        self._modules[spec.name] = loaded
        logger.info("%s %s %s", LogTag.PLUGIN, "↩" if loaded.legacy else "✓", spec.name)
        return loaded

    async def load_all(self) -> None:
        for spec in discover_modules():
            await self.load(spec)
        statuses = [module.status for module in self._modules.values()]
        logger.info(
            "%s Modules ready | loaded=%s failed=%s",
            LogTag.TELEGRAM,
            statuses.count("loaded"),
            statuses.count("failed"),
        )


plugin_manager = PluginManager(Kenzo)
