"""Bot module system: discovery, loading and the registration API (see ``manager.py``)."""

from app.telegram.plugins.context import PluginContext
from app.telegram.plugins.manager import (
    LoadedModule,
    ModuleSpec,
    PluginManager,
    RequiredModuleError,
    discover_modules,
    plugin_manager,
)

__all__ = [
    "LoadedModule",
    "ModuleSpec",
    "PluginContext",
    "PluginManager",
    "RequiredModuleError",
    "discover_modules",
    "plugin_manager",
]
