import ast
import asyncio
import os
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from app import Kenzo
from app.db.crud.keyboards import KeyboardButtonCRUD
from app.db.crud.settings import SettingsManager
from app.jobs.scheduler import start_scheduler
from app.logger import LogTag, get_logger
from app.logger.telethon import register_telethon_client, unregister_telethon_client
from app.telegram.middlewares import register_global_middlewares
from app.telegram.shared.utils.plugins import PluginLoadError, load_plugins_collect_errors
from app.version import log_runtime_versions
from config import BOT_TOKEN

logger = get_logger(__name__)

_TELEGRAM_ROOT = Path(__file__).resolve().parent
_APP_ROOT = Path(__file__).resolve().parent.parent
_SCANNED_DIRS = ("admin", "user", "business")
# Only __init__.py is not a plugin entry point; all other *.py modules are loaded.
_SKIPPED_FILES = frozenset({"__init__.py"})


@dataclass(frozen=True)
class TelegramModuleSpec:
    canonical_name: str
    import_name: str
    path: Path
    enabled: bool
    order: int


@dataclass
class TelegramLoadStats:
    loaded: int = 0
    legacy_imported: int = 0
    disabled: int = 0
    skipped: int = 0
    duplicates: int = 0
    failed: int = 0


def _disabled_module_names() -> frozenset[str]:
    raw = os.getenv("DISABLED_TELEGRAM_MODULES", "")
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def _static_metadata(module_path: Path) -> dict[str, object]:
    metadata: dict[str, object] = {}
    try:
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError) as exc:
        logger.warning("%s Could not read module metadata from %s: %s", LogTag.TELEGRAM, module_path, exc)
        return metadata

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in {"MODULE_NAME", "MODULE_ENABLED", "MODULE_ORDER"}:
                try:
                    metadata[target.id] = ast.literal_eval(node.value)
                except ValueError, SyntaxError:
                    continue
    return metadata


def _canonical_name_for_path(module_path: Path) -> str | None:
    rel_to_telegram = module_path.relative_to(_TELEGRAM_ROOT)
    parts = rel_to_telegram.parts

    if module_path.name == "module.py" and len(parts) == 3:
        return ".".join((parts[0], parts[1]))
    if module_path.stem.endswith("_legacy"):
        canonical_stem = module_path.stem[: -len("_legacy")]
        package_module = module_path.with_name(canonical_stem) / "module.py"
        if package_module.is_file():
            return None
        return ".".join((*parts[:-1], canonical_stem))
    if len(parts) == 2:
        return ".".join((parts[0], module_path.stem))
    return None


def _import_name_for_path(module_path: Path) -> str:
    rel = module_path.relative_to(_APP_ROOT).with_suffix("")
    return ".".join(("app", *rel.parts))


def _iter_candidate_paths() -> Iterable[Path]:
    for dirname in _SCANNED_DIRS:
        root = _TELEGRAM_ROOT / dirname
        if not root.is_dir():
            continue
        yield from sorted(root.glob("*.py"))
        yield from sorted(root.glob("*/module.py"))


def _discover_plugin_modules() -> tuple[list[TelegramModuleSpec], TelegramLoadStats]:
    disabled_names = _disabled_module_names()
    seen_names: set[str] = set()
    seen_imports: set[str] = set()
    specs: list[TelegramModuleSpec] = []
    stats = TelegramLoadStats()

    for module_path in _iter_candidate_paths():
        rel_to_telegram = module_path.relative_to(_TELEGRAM_ROOT)
        if any(part.startswith("_") or part == "__pycache__" for part in rel_to_telegram.parts):
            stats.skipped += 1
            logger.debug("%s Skipping private module path: %s", LogTag.TELEGRAM, module_path.resolve())
            continue
        if module_path.name.startswith("!") or module_path.name in _SKIPPED_FILES:
            stats.skipped += 1
            logger.info("%s Skipping module by rule: %s", LogTag.TELEGRAM, module_path.resolve())
            continue

        canonical_name = _canonical_name_for_path(module_path)
        if canonical_name is None:
            stats.skipped += 1
            logger.debug("%s Skipping unsupported module path: %s", LogTag.TELEGRAM, module_path.resolve())
            continue

        import_name = _import_name_for_path(module_path)
        if import_name in seen_imports:
            stats.duplicates += 1
            logger.warning("%s Duplicate import skipped: %s at %s", LogTag.PLUGIN, import_name, module_path.resolve())
            continue

        metadata = _static_metadata(module_path)
        canonical_name = str(metadata.get("MODULE_NAME") or canonical_name)
        enabled = bool(metadata.get("MODULE_ENABLED", True))
        order = int(metadata.get("MODULE_ORDER", 1000))

        if canonical_name in seen_names:
            stats.duplicates += 1
            logger.warning(
                "%s Duplicate module skipped: %s at %s", LogTag.PLUGIN, canonical_name, module_path.resolve()
            )
            continue

        if canonical_name in disabled_names:
            stats.disabled += 1
            logger.info("%s Module disabled by env: %s", LogTag.TELEGRAM, canonical_name)
            continue
        if not enabled:
            stats.disabled += 1
            logger.info("%s Module disabled (MODULE_ENABLED=False): %s", LogTag.TELEGRAM, canonical_name)
            continue

        seen_names.add(canonical_name)
        seen_imports.add(import_name)
        specs.append(
            TelegramModuleSpec(
                canonical_name=canonical_name,
                import_name=import_name,
                path=module_path.resolve(),
                enabled=enabled,
                order=order,
            )
        )

    return sorted(specs, key=lambda spec: (spec.order, spec.canonical_name)), stats


def _module_from_sys_modules(import_name: str) -> ModuleType | None:
    module = sys.modules.get(import_name)
    if isinstance(module, ModuleType):
        return module
    return None


def _register_module_entrypoint(spec: TelegramModuleSpec, module: ModuleType) -> str:
    setup = getattr(module, "setup", None)
    register = getattr(module, "register", None)
    if callable(setup):
        setup(Kenzo)
        return "loaded"
    if callable(register):
        register(Kenzo)
        return "loaded"
    return "legacy_imported"


async def load_plugins_telethon():
    """Loading robot plugins"""
    failures: list[tuple[str, Path, BaseException]] = []
    specs, stats = _discover_plugin_modules()

    for spec in specs:
        ok, _path, exc = load_plugins_collect_errors(spec.import_name, spec.path)
        if ok:
            module = _module_from_sys_modules(spec.import_name)
            try:
                status = _register_module_entrypoint(spec, module) if module is not None else "legacy_imported"
                if status == "loaded":
                    stats.loaded += 1
                else:
                    stats.legacy_imported += 1
                mark = "↩" if status == "legacy_imported" else "✓"
                logger.info(
                    "%s %s %s (%s)",
                    LogTag.PLUGIN,
                    mark,
                    spec.canonical_name,
                    spec.path.name,
                )
            except Exception as setup_exc:
                failures.append((spec.import_name, spec.path, setup_exc))
                stats.failed += 1
            continue
        stats.failed += 1
        failures.append((spec.import_name, spec.path, exc or RuntimeError("unknown error")))

    if failures:
        logger.error("%s %s", LogTag.PLUGIN, "=" * 60)
        logger.error(
            "%s LOAD FAILED — %s of %s module(s) did not load",
            LogTag.PLUGIN,
            len(failures),
            stats.loaded + stats.legacy_imported + len(failures),
        )
        for module_name, module_path, exc in failures:
            logger.error("%s %s", LogTag.PLUGIN, "-" * 60)
            logger.error("%s File:   %s", LogTag.PLUGIN, module_path)
            logger.error("%s Module: %s", LogTag.PLUGIN, module_name)
            logger.error("%s Error:  %s: %s", LogTag.PLUGIN, type(exc).__name__, exc)
        logger.error("%s %s", LogTag.PLUGIN, "=" * 60)
        raise PluginLoadError(failures)

    logger.info(
        "%s Plugins ready | loaded=%s legacy=%s disabled=%s skipped=%s failed=%s total=%s",
        LogTag.TELEGRAM,
        stats.loaded,
        stats.legacy_imported,
        stats.disabled,
        stats.skipped,
        stats.failed,
        stats.loaded + stats.legacy_imported,
    )


async def run_telethon(stop_event: asyncio.Event | None = None):
    await SettingsManager().add_default_settings()
    await KeyboardButtonCRUD().initialize_default_buttons()
    await Kenzo.start(bot_token=BOT_TOKEN)
    register_telethon_client(Kenzo)
    logger.info("%s Bot connected", LogTag.TELEGRAM)
    log_runtime_versions()

    register_global_middlewares()

    await load_plugins_telethon()

    start_scheduler()

    # Resume any running broadcast from its persisted cursor after restart.
    from app.services.broadcast.manager import broadcast_manager

    await broadcast_manager.resume_running_broadcasts()

    from app.telegram.admin.send2all.callbacks import resume_broadcast_monitors

    await resume_broadcast_monitors()

    async def _stopper():
        if stop_event is None:
            return
        await stop_event.wait()
        unregister_telethon_client(Kenzo)
        await Kenzo.disconnect()
        logger.info("%s Bot disconnected", LogTag.TELEGRAM)

    stopper = asyncio.create_task(_stopper())
    try:
        await Kenzo.run_until_disconnected()
    finally:
        stopper.cancel()
        unregister_telethon_client(Kenzo)
