"""Stats payload builders and formatters for admin info bot."""

import asyncio
import json
import os
import platform
import shutil
import time
from datetime import datetime, timedelta

from telethon.tl.functions.help import GetConfigRequest

from app import Kenzo
from app.db.crud.cryptopayments import (
    get_crypto_period_breakdown,
    get_global_crypto_breakdown,
)
from app.db.crud.services import ServiceCRUD
from app.db.crud.settings import SettingsManager
from app.db.crud.transactions import TransactionCRUD
from app.db.crud.user import UserCRUD
from app.logger import get_logger
from app.logger.tags import LogTag
from app.telegram.admin.info_bot.states import (
    HIDDEN_LINK,
    REVENUE_PERIODS,
    STATS_CACHE_TTL,
    TEHRAN_TZ,
    UTC_TZ,
)
from app.telegram.state.store import get_app_cache, set_app_cache
from app.utils.formatting.dates import Time_Date
from app.utils.text.markdown import bold, code, quote
from app.version import VERSIONS

logger = get_logger(__name__)

user_crud = UserCRUD()
service_crud = ServiceCRUD()
tx_crud = TransactionCRUD()


def _stats_timestamps(now: datetime | None = None) -> dict:
    if now is None:
        now = _now_tehran()
    elif now.tzinfo is None:
        now = now.replace(tzinfo=UTC_TZ).astimezone(TEHRAN_TZ)
    else:
        now = now.astimezone(TEHRAN_TZ)
    today_start = datetime(now.year, now.month, now.day, tzinfo=TEHRAN_TZ)
    return {
        "today_ts": int(today_start.timestamp()),
        "yesterday_ts": int((today_start - timedelta(days=1)).timestamp()),
        "week_ts": int((today_start - timedelta(days=7)).timestamp()),
        "month_ts": int((today_start - timedelta(days=30)).timestamp()),
        "day_ts": int((now - timedelta(days=1)).timestamp()),
        "day_2_ts": int((now - timedelta(days=2)).timestamp()),
        "day_3_ts": int((now - timedelta(days=3)).timestamp()),
        "day_4_ts": int((now - timedelta(days=4)).timestamp()),
        "two_days_ago_ts": int((today_start - timedelta(days=2)).timestamp()),
        "three_days_ago_ts": int((today_start - timedelta(days=3)).timestamp()),
    }


def _now_utc() -> datetime:
    return datetime.now(UTC_TZ)


def _now_tehran() -> datetime:
    return _now_utc().astimezone(TEHRAN_TZ)


def _tehran_day_start(value: datetime | None = None) -> datetime:
    value = value.astimezone(TEHRAN_TZ) if value else _now_tehran()
    return datetime(value.year, value.month, value.day, tzinfo=TEHRAN_TZ)


def _month_start_tehran(value: datetime | None = None) -> datetime:
    value = value.astimezone(TEHRAN_TZ) if value else _now_tehran()
    return datetime(value.year, value.month, 1, tzinfo=TEHRAN_TZ)


def _stats_period_range(period: str) -> dict:
    """Return Tehran calendar bounds converted to UTC timestamps for database queries."""
    today = _tehran_day_start()
    tomorrow = today + timedelta(days=1)
    if period == "all":
        start, end = None, None
    elif period == "1d":
        start, end = today, tomorrow
    elif period == "yesterday":
        start, end = today - timedelta(days=1), today
    elif period == "7d_ago":
        start, end = today - timedelta(days=7), today - timedelta(days=6)
    elif period == "this_month":
        start, end = _month_start_tehran(), tomorrow
    elif period.endswith("d") and period[:-1].isdigit():
        days = max(1, int(period[:-1]))
        start, end = today - timedelta(days=days - 1), tomorrow
    elif period.endswith("m") and period[:-1].isdigit():
        days = max(1, int(period[:-1])) * 30
        start, end = today - timedelta(days=days - 1), tomorrow
    else:
        start, end = today, tomorrow

    return {
        "period": period,
        "start_ts": 0 if start is None else int(start.astimezone(UTC_TZ).timestamp()),
        "end_ts": None if end is None else int(end.astimezone(UTC_TZ).timestamp()),
    }


def _to_datetime(value: str | None) -> datetime:
    if not value:
        return _now_utc()
    try:
        dt = datetime.fromisoformat(value)
        return dt.replace(tzinfo=UTC_TZ) if dt.tzinfo is None else dt.astimezone(UTC_TZ)
    except ValueError:
        return _now_utc()


def _relative_precise(updated_at: datetime) -> str:
    updated_at = updated_at.replace(tzinfo=UTC_TZ) if updated_at.tzinfo is None else updated_at.astimezone(UTC_TZ)
    sec = max(0, int((_now_utc() - updated_at).total_seconds()))
    if sec < 60:
        return f"{sec} ثانیه قبل"
    if sec < 3600:
        return f"{sec // 60} دقیقه قبل"
    if sec < 86400:
        return f"{sec // 3600} ساعت قبل"
    return f"{sec // 86400} روز قبل"


def _fmt_updated(updated_at: datetime) -> str:
    td = Time_Date(updated_at)
    if "error" in td:
        return f"{updated_at.strftime('%Y-%m-%d %H:%M:%S')} · {_relative_precise(updated_at)}"
    return f"{td['jf']} · {_relative_precise(updated_at)}"


def _fmt_bytes(num: int) -> str:
    if num <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{num} B"


def _irt_to_usd(amount_irt: int, arz_usd: int) -> float:
    """Convert full TOMAN amount to USD (arz_usd = TOMAN per 1 USD)."""
    if not amount_irt or not arz_usd:
        return 0.0
    return amount_irt / arz_usd


def _bar(percent: float, width: int = 10) -> str:
    pct = max(0.0, min(100.0, percent))
    filled = round((pct / 100) * width)
    return "█" * filled + "░" * (width - filled)


async def _cached_json(key: str, producer, force: bool = False) -> dict:
    if not force:
        raw = await get_app_cache(key)
        if raw:
            try:
                data = json.loads(raw)
                logger.info("%s stats cache HIT key=%s bytes=%s", LogTag.REDIS, key, len(raw))
                data["_cache_meta"] = {"source": "hit", "key": key}
                return data
            except json.JSONDecodeError:
                logger.warning("%s stats cache corrupt key=%s", LogTag.REDIS, key)
    data = await producer()
    store = {k: v for k, v in data.items() if not str(k).startswith("_")}
    await set_app_cache(key, json.dumps(store, ensure_ascii=False), ttl_seconds=STATS_CACHE_TTL)
    logger.info("%s stats cache MISS key=%s ttl=%ss", LogTag.REDIS, key, STATS_CACHE_TTL)
    data["_cache_meta"] = {"source": "miss", "key": key, "ttl": STATS_CACHE_TTL}
    return data


async def _measure_ping() -> float:
    """Legacy Telethon ping style (seconds, shown as ms like before)."""
    t0 = time.perf_counter()
    await Kenzo(GetConfigRequest())
    return time.perf_counter() - t0


def _collect_system_metrics() -> dict:
    disk_path = "C:\\" if platform.system() == "Windows" else "/"
    try:
        import psutil

        cpu_cores = psutil.cpu_count(logical=True) or os.cpu_count() or 0
        cpu_pct = psutil.cpu_percent(interval=0.3)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage(disk_path)
        disk_pct = (disk.used / disk.total * 100) if disk.total else 0.0
        return {
            "cpu_percent": round(cpu_pct, 1),
            "cpu_cores": int(cpu_cores),
            "ram_percent": round(mem.percent, 1),
            "ram_used": int(mem.used),
            "ram_total": int(mem.total),
            "disk_percent": round(disk_pct, 1),
            "disk_used": int(disk.used),
            "disk_total": int(disk.total),
            "platform": platform.platform(),
            "python": platform.python_version(),
        }
    except Exception as exc:
        logger.warning("psutil unavailable, using fallback metrics: %s", exc)
        disk = shutil.disk_usage(disk_path)
        disk_pct = (disk.used / disk.total * 100) if disk.total else 0.0
        return {
            "cpu_percent": 0.0,
            "cpu_cores": os.cpu_count() or 0,
            "ram_percent": 0.0,
            "ram_used": 0,
            "ram_total": 0,
            "disk_percent": round(disk_pct, 1),
            "disk_used": int(disk.used),
            "disk_total": int(disk.total),
            "platform": platform.platform(),
            "python": platform.python_version(),
        }


async def main_payload(force: bool = False) -> dict:
    async def _produce() -> dict:
        ts = _stats_timestamps()
        user_stats, sales, pending = await asyncio.gather(
            user_crud.get_user_stats(
                month_ts=ts["month_ts"],
                week_ts=ts["week_ts"],
                day_ts=ts["day_ts"],
                day_2_ts=ts["day_2_ts"],
                day_3_ts=ts["day_3_ts"],
                day_4_ts=ts["day_4_ts"],
                today_ts=ts["today_ts"],
            ),
            tx_crud.get_dashboard_sales(ts),
            tx_crud.get_pending_manual_summary(),
        )
        return {
            "updated_at": _now_utc().isoformat(),
            "users": user_stats,
            "sales": sales,
            "pending": pending,
        }

    return await _cached_json("stats:main", _produce, force=force)


def main_text(payload: dict) -> str:
    u = payload["users"]
    s = payload["sales"]
    p = payload["pending"]
    inactive = u["banned"] + u["blocked"] + u["deleted"]
    updated_at = _to_datetime(payload.get("updated_at"))

    lines = [
        HIDDEN_LINK,
        f"👥 {bold('آمار کاربران')}",
        f"👤 {bold('کل کاربران:')} {code(f'{u["total"]:,}')}",
        f"✅ {bold('کاربران فعال:')} {code(f'{u["active"]:,}')}",
        "",
        f"📈 {bold('عضویت جدید')}",
        f"🗓 {bold('امروز:')} {code(f'{u.get("members_today", 0):,}')}",
        f"🗓 {bold('دیروز:')} {code(f'{u.get("members_1d_ago", 0):,}')}",
        f"🗓 {bold('۲ روز پیش:')} {code(f'{u.get("members_2d_ago", 0):,}')}",
        f"🗓 {bold('۳ روز پیش:')} {code(f'{u.get("members_3d_ago", 0):,}')}",
        f"📊 {bold('هفته:')} {code(f'{u["members_week"]:,}')} · {bold('ماه:')} {code(f'{u["members_month"]:,}')}",
        "",
        f"🚫 {bold('غیرفعال')} {code(f'({inactive:,})')}",
        f"🔒 {bold('بن:')} {code(f'{u["banned"]:,}')} · 🚫 {bold('بلاک:')} {code(f'{u["blocked"]:,}')} · 🗑 {bold('حذف:')} {code(f'{u["deleted"]:,}')}",
        "",
        f"💳 {bold('کارت‌به‌کارت در انتظار تایید')}",
        f"⏳ {bold('تعداد:')} {code(f'{p["count"]:,}')} · 💰 {bold('مبلغ:')} {code(f'{p["amount"]:,}')} تومان",
        "",
        f"💰 {bold('خلاصه فروش')}",
        f"📅 {bold('امروز:')} {code(f'{s["sales_today"]:,}')} تومان",
        f"📅 {bold('دیروز:')} {code(f'{s["sales_yesterday"]:,}')} تومان",
        f"📅 {bold('۲ روز پیش:')} {code(f'{s["sales_2d_ago"]:,}')} تومان",
        f"📅 {bold('۳ روز پیش:')} {code(f'{s["sales_3d_ago"]:,}')} تومان",
        f"📊 {bold('۷ روز اخیر:')} {code(f'{s["sales_7d"]:,}')} تومان",
        "",
    ]
    cache_line = _format_cache_meta(payload)
    if cache_line:
        lines.append(cache_line)
        lines.append("")
    lines.extend(
        [
            f"🕒 {bold('آخرین بروزرسانی:')} {code(_fmt_updated(updated_at))}",
            quote("Coded By @AmirKenzoo"),
        ]
    )
    return "\n".join(lines)


async def _revenue_payload(period: str, force: bool = False) -> dict:
    async def _produce() -> dict:
        period_range = _stats_period_range(period)
        start = period_range["start_ts"]
        end = period_range["end_ts"]
        settings = await SettingsManager().get_settings()
        arz_usd = int(getattr(settings, "arz_usd", 0) or 0)
        breakdown, crypto = await asyncio.gather(
            tx_crud.get_breakdown(start, end),
            get_crypto_period_breakdown(start, end) if period != "all" else get_global_crypto_breakdown(),
        )
        return {
            "updated_at": _now_utc().isoformat(),
            "period": period,
            "range": period_range,
            "arz_usd": arz_usd,
            "breakdown": breakdown,
            "crypto": crypto,
        }

    return await _cached_json(f"stats:revenue:{period}", _produce, force=force)


def _revenue_text(payload: dict) -> str:
    b = payload["breakdown"]
    cr = payload["crypto"]
    period = payload.get("period", "1d")
    updated_at = _to_datetime(payload.get("updated_at"))
    label = REVENUE_PERIODS.get(period, period)
    arz_usd = int(payload.get("arz_usd", 0) or 0)

    currencies = [c for c in (cr.get("currencies") or []) if int(c.get("count", 0) or 0) > 0]

    def _line(emoji: str, title: str, count: int, amount: int) -> str:
        if not count:
            return f"{emoji} {bold(title)}: —"
        return f"{emoji} {bold(title)}: {code(f'{count:,}')} تراکنش · {code(f'{amount:,}')} تومان"

    total_sales = b["manual_approved_sum"] + b["auto_approved_sum"] + int(cr.get("total_amount", 0) or 0)
    total_tx = b["manual_approved_count"] + b["auto_approved_count"] + int(cr.get("count", 0) or 0)

    lines = [
        f"💰 {bold('گزارش مالی')} — {label}",
        "",
        f"📊 {bold('کل فروش بازه')}",
        f"💵 {code(f'{total_sales:,}')} تومان · {code(f'{total_tx:,}')} تراکنش",
        "",
        f"💳 {bold('کارت‌به‌کارت دستی')}",
        _line("✅", "تایید شده", b["manual_approved_count"], b["manual_approved_sum"]),
        _line("❌", "رد شده", b["manual_rejected_count"], b["manual_rejected_sum"]),
        f"⏳ {bold('در انتظار (کل صف):')} {code(f'{b["manual_pending_total_count"]:,}')} · {code(f'{b["manual_pending_total_sum"]:,}')} تومان",
        "",
        f"🤖 {bold('کارت‌به‌کارت خودکار')}",
        _line("✅", "تایید شده", b["auto_approved_count"], b["auto_approved_sum"]),
    ]

    if currencies:
        crypto_usd_total = 0.0
        lines.append("")
        lines.append(f"💎 {bold('ارز دیجیتال')}")
        for item in currencies:
            arz = item["arz"]
            crypto_vol = item["crypto_sum"]
            vol_str = f"{crypto_vol:,.4f}".rstrip("0").rstrip(".")
            irt = item["amount_irt"]
            usd = _irt_to_usd(irt, arz_usd)
            crypto_usd_total += usd
            lines.append(f"🔹 {bold(arz)}: {code(vol_str)} {arz} · {code(f'{irt:,}')} TOMAN · ${code(f'{usd:,.2f}')}")
        lines.append(f"💵 {bold('جمع دلاری ارزها:')} ${code(f'{crypto_usd_total:,.2f}')}")

    lines.extend(
        [
            "",
            f"🕒 {bold('آخرین بروزرسانی:')} {code(_fmt_updated(updated_at))}",
        ]
    )
    return "\n".join(lines)


async def _services_payload(period: str, force: bool = False) -> dict:
    async def _produce() -> dict:
        period_range = _stats_period_range(period)
        stats = await service_crud.get_period_stats(
            period_range["start_ts"],
            period_range["end_ts"],
        )
        return {
            "updated_at": _now_utc().isoformat(),
            "period": period,
            "range": period_range,
            "stats": stats,
        }

    return await _cached_json(f"stats:services:{period}", _produce, force=force)


def _services_text(payload: dict) -> str:
    s = payload["stats"]
    period = payload.get("period", "1d")
    updated_at = _to_datetime(payload.get("updated_at"))
    label = REVENUE_PERIODS.get(period, period)

    lines = [
        f"📡 {bold('آمار سرویس‌ها')} — {label}",
        "",
        f"📊 {bold('کل سرویس‌ها')}",
        f"📦 {bold('کل:')} {code(f'{s["total"]:,}')} · ✅ {bold('فعال:')} {code(f'{s["active"]:,}')} · ⛔ {bold('غیرفعال:')} {code(f'{s["disabled"]:,}')}",
        "",
        f"🆕 {bold('ساخته‌شده در بازه')}",
        f"💎 {bold('پولی:')} {code(f'{s["paid_period"]:,}')} · 🧪 {bold('تست:')} {code(f'{s["test_period"]:,}')}",
        "",
        f"📈 {bold('انواع سرویس (کل)')}",
        f"💎 {bold('پولی:')} {code(f'{s["paid_total"]:,}')} · 🧪 {bold('تست:')} {code(f'{s["test_total"]:,}')}",
        f"💾 {bold('حجم کل:')} {code(_fmt_bytes(s['total_volume_bytes']))}",
        "",
        f"⏰ {bold('انقضا')}",
        f"⚠️ {bold('۳ روز آینده:')} {code(f'{s["expiring_3d"]:,}')} · 📅 {bold('۷ روز آینده:')} {code(f'{s["expiring_7d"]:,}')} · ❌ {bold('منقضی:')} {code(f'{s["expired"]:,}')}",
    ]

    if s.get("top_panels"):
        lines.append("")
        lines.append(f"🏆 {bold('پرترداف پنل‌ها (بازه)')}")
        for name, cnt in s["top_panels"]:
            lines.append(f"• {bold(name)}: {code(f'{cnt:,}')}")

    if s.get("top_volumes"):
        lines.append("")
        lines.append(f"📦 {bold('پرفروش‌ترین حجم‌ها (بازه)')}")
        for vol_label, cnt in s["top_volumes"]:
            lines.append(f"• {bold(vol_label)}: {code(f'{cnt:,}')}")

    cache_line = _format_cache_meta(payload)
    if cache_line:
        lines.extend(["", cache_line])
    lines.extend(
        [
            "",
            f"🕒 {bold('آخرین بروزرسانی:')} {code(_fmt_updated(updated_at))}",
        ]
    )
    return "\n".join(lines)


async def _system_payload(force: bool = False) -> dict:
    async def _produce() -> dict:
        settings = await SettingsManager().get_settings()
        metrics = _collect_system_metrics()
        return {
            "updated_at": _now_utc().isoformat(),
            "bot_mode": bool(getattr(settings, "bot_mode", True)),
            "sale_mode": bool(getattr(settings, "sale_mode", True)),
            "arz_usd": int(getattr(settings, "arz_usd", 0) or 0),
            "arz_trx": int(getattr(settings, "arz_trx", 0) or 0),
            "arz_ton": int(getattr(settings, "arz_ton", 0) or 0),
            **metrics,
        }

    return await _cached_json("stats:system", _produce, force=force)


def _format_cache_meta(payload: dict) -> str:
    meta = payload.get("_cache_meta") or {}
    source = meta.get("source")
    if source == "hit":
        return f"📦 {bold('کش آمار:')} {code('HIT')} · {code(meta.get('key', '—'))}"
    if source == "miss":
        return (
            f"📦 {bold('کش آمار:')} {code('MISS')} · {code(meta.get('key', '—'))}"
            f" · TTL {code(str(meta.get('ttl', STATS_CACHE_TTL)))}s"
        )
    return ""


def _system_text(payload: dict, ping_sec: float) -> str:
    updated_at = _to_datetime(payload.get("updated_at"))
    cpu = payload["cpu_percent"]
    ram = payload["ram_percent"]
    disk = payload["disk_percent"]
    lines = [
        f"🧪 {bold('وضعیت سیستم')}",
        f"🚀 {bold('پینگ ربات:')} {code(f'{ping_sec:.3f} ms')}",
        "",
        f"🖥 {bold('CPU')} ({code(str(payload.get('cpu_cores', 0)))} هسته)",
        f"{_bar(cpu)} {code(f'{cpu}%')}",
        "",
        f"🧠 {bold('RAM')}",
        f"{_bar(ram)} {code(f'{ram}%')} · {code(_fmt_bytes(payload['ram_used']))} / {code(_fmt_bytes(payload['ram_total']))}",
        "",
        f"💽 {bold('Disk')}",
        f"{_bar(disk)} {code(f'{disk}%')} · {code(_fmt_bytes(payload['disk_used']))} / {code(_fmt_bytes(payload['disk_total']))}",
        "",
        f"📚 Telethon {code(VERSIONS.telethon)} · FastAPI {code(VERSIONS.fastapi)} · Bot {code(VERSIONS.app)}",
        f"🐍 Python {code(payload.get('python', '-'))}",
    ]
    lines.extend(["", f"🕒 {bold('آخرین بروزرسانی:')} {code(_fmt_updated(updated_at))}"])
    return "\n".join(lines)
