"""Seed a DEV database with usable data for local development and ForApp testing.

Runs as a one-shot container in docker-compose.dev.yml AFTER migrations::

    docker compose -f docker-compose.dev.yml --env-file .env.dev up --build

Safety: refuses to run unless ``PASARGUARDBOT_DEV_SEED=1`` is set, and refuses
when the database name does not look like a dev database (must contain
``dev``, ``test`` or ``sqlite``). NEVER point this at production.

What it creates (all idempotent — safe to re-run):
  - default settings row, with ``pay_mode=True`` and ``forapp_enabled=True``
  - one active manual card (obviously fake number)
  - one DISABLED panel (code 9001) + 3 plans on it
  - two test users (ids 100000001/100000002, zero balance)
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path (`uv run scripts/seed_dev.py` entry point).
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

DEV_USER_IDS = (100000001, 100000002)
DEV_PANEL_CODE = 9001
DEV_CARD_NUMBER = "6037991234567890"
DEV_CARD_NAME = "Dev Test Card"


def _refuse(reason: str) -> int:
    print(f"seed_dev: REFUSED — {reason}", file=sys.stderr)
    return 1


def _dev_seed_enabled() -> bool:
    if os.getenv("PASARGUARDBOT_DEV_SEED") == "1":
        return True
    # Local runs use a `.env` file (docker injects real env vars instead).
    try:
        from decouple import Config, RepositoryEnv

        return Config(RepositoryEnv(".env"))("PASARGUARDBOT_DEV_SEED", default="") == "1"
    except Exception:
        return False


async def _seed() -> None:
    from app.db.crud.cards import ManualCardManager
    from app.db.crud.panels import PanelsManager
    from app.db.crud.plans import PlanManager
    from app.db.crud.settings import SettingsManager
    from app.db.crud.user import UserManager
    from config import FORAPP_API_KEYS, SQLALCHEMY_DATABASE_URL

    url = SQLALCHEMY_DATABASE_URL or ""
    lowered = url.lower()
    if not any(mark in lowered for mark in ("dev", "test", "sqlite", ":memory:")):
        raise RuntimeError(f"database URL does not look like a dev database: {url!r}")

    manager = SettingsManager()
    await manager.add_default_settings()
    settings = await manager.get_settings()
    await manager.update_setting(settings.id, pay_mode=True, forapp_enabled=True)
    print("settings: pay_mode=True, forapp_enabled=True")

    cards = await ManualCardManager().get_all_cards()
    if not any(c.number == DEV_CARD_NUMBER for c in cards):
        created = await ManualCardManager().add_card(number=DEV_CARD_NUMBER, name=DEV_CARD_NAME, active=True)
        if created is None:
            raise RuntimeError("failed to insert dev manual card")
        print(f"card: added active {DEV_CARD_NUMBER} ({DEV_CARD_NAME})")
    else:
        print("card: already present")

    panels = PanelsManager()
    if await panels.get_panel_by_code(DEV_PANEL_CODE) is None:
        await panels.add_panel(
            code=DEV_PANEL_CODE,
            name="Dev Panel (disabled)",
            enable=False,
            base_url="http://127.0.0.1:9999",
            username="dev",
            password="dev",
            cookie="dev",
        )
        print(f"panel: added disabled panel code={DEV_PANEL_CODE}")
    else:
        print("panel: already present")

    plans = PlanManager()
    existing = await plans.get_all_plans(panel_code=DEV_PANEL_CODE)
    if not existing:
        await plans.add_plan(price=50000, storage=10, duration=30, panel_code=DEV_PANEL_CODE)
        await plans.add_plan(price=120000, storage=30, duration=30, panel_code=DEV_PANEL_CODE)
        await plans.add_plan(price=300000, storage=100, duration=90, panel_code=DEV_PANEL_CODE)
        print("plans: added 3 plans (50k/120k/300k toman)")
    else:
        print(f"plans: already present ({len(existing)})")

    users = UserManager()
    for uid in DEV_USER_IDS:
        if await users.get_user_by_id(uid) is None:
            await users.create_user(uid)
            print(f"user: created {uid}")
        else:
            print(f"user: {uid} already present")

    print("----")
    print("DEV SEED DONE. ForApp smoke test against this stack:")
    print("  curl -s http://127.0.0.1:6170/api/payments/forapp/health")
    print("  curl -s -X POST http://127.0.0.1:6170/api/payments/forapp/webhook \\")
    print(f"    -H 'X-API-Key: {(FORAPP_API_KEYS or '').split(',')[0].strip() or '<key-from-.env.dev>'}' \\")
    print("    -H 'Content-Type: application/json' \\")
    print("    -d '{\"id\":\"dev-probe-1\",\"test\":true,\"sender\":\"ForApp\",")
    print("        \"bank\":\"test\",\"body\":\"probe\",\"amount\":1000123,\"unit\":\"rial\",")
    print("        \"is_deposit\":true,\"attempt\":1}'")


def main() -> int:
    if not _dev_seed_enabled():
        return _refuse("set PASARGUARDBOT_DEV_SEED=1 to run (dev databases only)")
    try:
        asyncio.run(_seed())
    except Exception as exc:  # seed must fail loudly, not silently
        print(f"seed_dev: FAILED — {exc!r}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
