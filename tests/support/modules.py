"""Load a source file as a standalone module.

Only for tests that must import a module while parts of the ``app`` package are
replaced with fakes; everything else should use a normal ``import``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_module_from_path(name: str, relative_path: str) -> ModuleType:
    """Execute ``relative_path`` (from the project root) and register it as ``name``."""
    spec = importlib.util.spec_from_file_location(name, PROJECT_ROOT / relative_path)
    assert spec and spec.loader, f"cannot load {relative_path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
