"""Module discovery and loading: entry points, metadata, failure isolation."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

from app.telegram.plugins import ModuleSpec, PluginManager, RequiredModuleError, manager as pm

PACKAGE = "fake_bot_modules"


class FakeClient:
    def __init__(self) -> None:
        self.handlers: list[tuple[object, object]] = []

    def add_event_handler(self, callback, event) -> None:
        self.handlers.append((callback, event))


@pytest.fixture
def write_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / PACKAGE
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    def write(name: str, source: str, *, required: bool = False) -> ModuleSpec:
        path = root / f"{name}.py"
        path.write_text(textwrap.dedent(source), encoding="utf-8")
        return ModuleSpec(name=name, import_name=f"{PACKAGE}.{name}", path=path, required=required)

    yield write
    for name in [m for m in sys.modules if m == PACKAGE or m.startswith(f"{PACKAGE}.")]:
        del sys.modules[name]


@pytest.mark.parametrize(
    "source",
    [
        "from telethon import events\nasync def h(e): pass\ndef setup(ctx):\n    ctx.add_event_handler(h, events.Raw())\n",
        "from telethon import events\nasync def h(e): pass\nasync def setup(ctx):\n    ctx.add_event_handler(h, events.Raw())\n",
        "from telethon import events\nasync def h(e): pass\ndef register(client):\n    client.add_event_handler(h, events.Raw())\n",
    ],
    ids=["setup", "async-setup", "register"],
)
async def test_entry_points(write_module, source: str) -> None:
    manager = PluginManager(FakeClient())  # type: ignore[arg-type]

    loaded = await manager.load(write_module("mod", source))

    assert (loaded.status, loaded.handlers, loaded.legacy) == ("loaded", 1, False)
    assert len(manager.client.handlers) == 1


async def test_module_without_entry_point_is_legacy(write_module) -> None:
    manager = PluginManager(FakeClient())  # type: ignore[arg-type]

    loaded = await manager.load(write_module("mod", "VALUE = 1\n"))

    assert (loaded.status, loaded.legacy) == ("loaded", True)


async def test_failing_optional_module_is_isolated(write_module) -> None:
    manager = PluginManager(FakeClient())  # type: ignore[arg-type]

    loaded = await manager.load(write_module("mod", "def setup(ctx):\n    raise RuntimeError('boom')\n"))

    assert (loaded.status, loaded.error) == ("failed", "RuntimeError: boom")
    assert manager.modules == (loaded,)


async def test_failing_required_module_aborts(write_module) -> None:
    manager = PluginManager(FakeClient())  # type: ignore[arg-type]
    spec = write_module("mod", "raise ImportError('missing')\n", required=True)

    with pytest.raises(RequiredModuleError):
        await manager.load(spec)


async def test_load_all_follows_discovery_order(write_module, monkeypatch: pytest.MonkeyPatch) -> None:
    source = "from telethon import events\nasync def h(e): pass\ndef setup(ctx):\n    ctx.add_event_handler(h, events.Raw())\n"
    specs = [write_module(name, source) for name in ("b", "a")]
    monkeypatch.setattr(pm, "discover_modules", lambda: specs)
    manager = PluginManager(FakeClient())  # type: ignore[arg-type]

    await manager.load_all()

    assert [cb.__module__ for cb, _ in manager.client.handlers] == [f"{PACKAGE}.b", f"{PACKAGE}.a"]


def test_discovery_reads_metadata_and_respects_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISABLED_TELEGRAM_MODULES", "admin.ping")
    specs = {spec.name: spec for spec in pm.discover_modules()}

    assert "admin.ping" not in specs
    games = specs["user.games"]
    assert games.import_name == "app.telegram.user.games.module"
    assert games.description == "User games and rewards"
    assert specs["user.start"].required
    assert list(specs) == [s.name for s in sorted(specs.values(), key=lambda s: (s.order, s.name))]


async def test_games_module_registers_its_handlers() -> None:
    spec = next(spec for spec in pm.discover_modules() if spec.name == "user.games")
    manager = PluginManager(FakeClient())  # type: ignore[arg-type]

    loaded = await manager.load(spec)

    assert (loaded.status, loaded.handlers) == ("loaded", 6)
