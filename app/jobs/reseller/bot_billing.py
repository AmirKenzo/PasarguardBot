"""Per-minute billing of bot resellers: read every live user from the panel, charge the new traffic.

One run for the whole bot. Users are read by id in batches of 500 spread over the minute, and
billing follows a counter that never goes back, so a failed batch or a skipped run only delays
a charge; it never loses or doubles one.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass

from app.db.crud.bot_reseller import BotResellerCRUD
from app.db.crud.panels import PanelsManager
from app.db.models.bot_reseller import RESELLER_ACTIVE, RESELLER_FROZEN, BotResellerUser
from app.logger import LogTag, get_logger
from app.services.bot_reseller import core, notify, panel as panel_api

log = get_logger(__name__)

WARN_LEVELS_HOURS = (24, 3)


@dataclass
class _RunStats:
    users: int = 0
    charged_resellers: int = 0
    charged_total: int = 0
    frozen: int = 0
    unfrozen: int = 0
    gone: int = 0
    failed_users: int = 0
    errors: int = 0


async def _read_counters(stats: _RunStats) -> dict[int, dict[int, int]]:
    """reseller id -> {user row id: traffic counter} for every user the panel answered for."""
    crud = BotResellerCRUD()
    users = await crud.live_users()
    stats.users = len(users)
    by_panel: dict[int, list[BotResellerUser]] = defaultdict(list)
    for user in users:
        by_panel[user.panel_code].append(user)

    counters: dict[int, dict[int, int]] = defaultdict(dict)
    now = int(time.time())
    for panel_code, panel_users in by_panel.items():
        panel = await PanelsManager().get_panel_by_code(code=panel_code)
        if panel is None:
            stats.failed_users += len(panel_users)
            continue
        found, failed = await panel_api.fetch_users(panel, [u.panel_user_id for u in panel_users])
        stats.failed_users += len(failed)
        for user in panel_users:
            if user.panel_user_id in failed:
                continue
            panel_user = found.get(user.panel_user_id)
            if panel_user is None:
                await crud.update_user(user.id, deleted_at=now)
                stats.gone += 1
                await notify.log_event(
                    "⚠️ یوزر نمایندگی ربات از پنل حذف شده بود",
                    [
                        f"👤 <b>یوزر:</b> <code>{user.username}</code>",
                        f"🧾 <b>نماینده:</b> <code>{user.reseller_id}</code>",
                    ],
                )
                continue
            counters[user.reseller_id][user.id] = panel_api.traffic_counter(panel_user)
    return counters


async def _warn_low_balance(reseller, balance: int) -> None:
    """Warn at each runway level once; the level resets when the wallet is topped up."""
    totals = await BotResellerCRUD().usage_totals(since=int(time.time()) - 86400, reseller_id=reseller.id)
    _, spent_24h = totals.get(reseller.id, (0, 0.0))
    burn_per_hour = spent_24h / 24
    if burn_per_hour <= 0:
        return
    hours_left = balance / burn_per_hour
    level = next((h for h in sorted(WARN_LEVELS_HOURS) if hours_left <= h), None)
    if level is None:
        if reseller.warned_hours is not None:
            await BotResellerCRUD().update_reseller(reseller.id, warned_hours=None)
        return
    if reseller.warned_hours is not None and reseller.warned_hours <= level:
        return
    await BotResellerCRUD().update_reseller(reseller.id, warned_hours=level)
    await notify.notify_reseller(
        reseller.telegram_id,
        "bot_reseller_low_balance",
        with_panel_button=True,
        balance=f"{balance:,}",
        hours=max(1, round(hours_left)),
    )


async def run_bot_reseller_billing() -> None:
    started = time.time()
    stats = _RunStats()
    crud = BotResellerCRUD()

    try:
        counters = await _read_counters(stats)
    except Exception as exc:
        log.error("bot reseller billing read failed: %s", exc, exc_info=True)
        return

    resellers = await crud.list_resellers()
    balances = await crud.balances(r.telegram_id for r in resellers)
    for reseller in resellers:
        try:
            balance = balances.get(reseller.telegram_id, 0)
            user_counters = counters.get(reseller.id)
            if user_counters:
                result = await crud.apply_usage(reseller.id, user_counters, await core.prices_for(reseller.id))
                if not result.ok:
                    stats.errors += 1
                    continue
                balance = result.balance
                if result.charged:
                    stats.charged_resellers += 1
                    stats.charged_total += result.charged

            if reseller.status == RESELLER_ACTIVE and balance <= 0:
                if user_counters:
                    await core.freeze(reseller, balance)
                    stats.frozen += 1
            elif reseller.status == RESELLER_FROZEN and balance > 0:
                await core.unfreeze(reseller)
                stats.unfrozen += 1
            elif reseller.status == RESELLER_ACTIVE and user_counters:
                await _warn_low_balance(reseller, balance)
        except Exception as exc:
            stats.errors += 1
            log.error("bot reseller billing failed reseller=%s: %s", reseller.id, exc, exc_info=True)

    log.info(
        f"{LogTag.JOB} bot_reseller_billing | duration={time.time() - started:.2f}s, users={stats.users}, "
        f"charged_resellers={stats.charged_resellers}, charged={stats.charged_total}, frozen={stats.frozen}, "
        f"unfrozen={stats.unfrozen}, gone={stats.gone}, unread={stats.failed_users}, errors={stats.errors}"
    )
