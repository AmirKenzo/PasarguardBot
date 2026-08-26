"""Top customers stats builder with tabbed views."""

import asyncio
from datetime import datetime

from telethon.tl import types

from app import CustomMarkdown
from app.db.crud.services import ServiceCRUD
from app.db.crud.transactions import TransactionCRUD
from app.services.telegram.rich_message import rt as _rt, rt_bold as _rt_bold
from app.utils.text.markdown import bold, code

tx_crud = TransactionCRUD()
service_crud = ServiceCRUD()

_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}
_DIVIDER = "─────────────────"

_TOP_VIEWS: tuple[tuple[str, str], ...] = (
    ("today", "⭐ امروز"),
    ("spend", "💰 مبلغ"),
    ("recharge", "🔢 شارژ"),
    ("config", "📦 کانفیگ"),
)


def _fmt_ts(ts: int) -> str:
    try:
        return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except ValueError, OSError:
        return str(ts)


def _rank_line(rank: int, uid: int | None, detail: str) -> str:
    prefix = _MEDALS.get(rank, f"{rank}.")
    uid_str = code(str(uid)) if uid is not None else code("?")
    return f"  {prefix} {uid_str} — {detail}"


def _section(emoji: str, title: str) -> list[str]:
    return ["", f"{emoji} {bold(title)}"]


async def build_top_customers_message(view: str = "today") -> tuple[str, list]:
    """Build top customers text. Views: today, spend, recharge, config."""
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    today_ts = int(today_start.timestamp())

    if view == "spend":
        top = await tx_crud.get_top_customers_by_spend(10)
        lines = [f"🏆 {bold('برترین مشتریان — مبلغ خرید کل')}", code(_DIVIDER)]
        if not top:
            lines.append("  • داده‌ای موجود نیست")
        else:
            for i, (uid, total, cnt) in enumerate(top, 1):
                lines.append(_rank_line(i, uid, f"{code(f'{total:,}')} تومان · {cnt} شارژ"))

    elif view == "recharge":
        top = await tx_crud.get_top_customers_by_tx_count(10)
        lines = [f"🏆 {bold('برترین مشتریان — تعداد شارژ')}", code(_DIVIDER)]
        if not top:
            lines.append("  • داده‌ای موجود نیست")
        else:
            for i, (uid, cnt, total) in enumerate(top, 1):
                lines.append(_rank_line(i, uid, f"{cnt} شارژ · {code(f'{total:,}')} تومان"))

    elif view == "config":
        top = await service_crud.get_top_customers_by_config_count(10)
        lines = [f"🏆 {bold('برترین مشتریان — تعداد کانفیگ')}", code(_DIVIDER)]
        if not top:
            lines.append("  • داده‌ای موجود نیست")
        else:
            for i, (uid, cnt) in enumerate(top, 1):
                lines.append(_rank_line(i, uid, f"{cnt} کانفیگ"))

    else:
        (
            top_spenders,
            top_recharge,
            config_stats,
            most_today,
            oldest,
            newest,
        ) = await asyncio.gather(
            tx_crud.get_top_spenders_today(today_ts, 5),
            tx_crud.get_top_recharge_today(today_ts, 5),
            service_crud.get_today_config_stats(today_ts, 5),
            tx_crud.get_most_spender_today(today_ts),
            tx_crud.get_oldest_customer(),
            tx_crud.get_newest_customer(),
        )

        lines = [f"🏆 {bold('برترین‌های امروز')}", code(_DIVIDER)]

        lines.extend(_section("👑", "بیشترین خرید امروز"))
        if most_today:
            uid, amount = most_today
            lines.append(f"  • {code(str(uid))} → {code(f'{amount:,}')} تومان")
        else:
            lines.append("  • هنوز خریدی ثبت نشده")

        lines.extend(_section("💰", "برترین خریداران (مبلغ)"))
        if top_spenders:
            for i, (uid, total, cnt) in enumerate(top_spenders, 1):
                lines.append(_rank_line(i, uid, f"{code(f'{total:,}')} تومان · {cnt} تراکنش"))
        else:
            lines.append("  • —")

        lines.extend(_section("🔢", "بیشترین شارژ (تعداد)"))
        if top_recharge:
            for i, (uid, cnt, total) in enumerate(top_recharge, 1):
                lines.append(_rank_line(i, uid, f"{cnt} شارژ · {code(f'{total:,}')} تومان"))
        else:
            lines.append("  • —")

        lines.extend(_section("📦", f"خرید کانفیگ — {config_stats['total_today']:,} عدد"))
        if config_stats["top_buyers"]:
            for i, (uid, cnt) in enumerate(config_stats["top_buyers"], 1):
                lines.append(_rank_line(i, uid, f"{cnt} کانفیگ"))
        else:
            lines.append("  • امروز کانفیگی فروخته نشده")

        lines.extend(_section("📌", "سوابق"))
        if oldest:
            uid, ts = oldest
            lines.append(f"  • قدیمی‌ترین: {code(str(uid))} · {code(_fmt_ts(ts))}")
        else:
            lines.append("  • قدیمی‌ترین: —")
        if newest:
            uid, ts = newest
            lines.append(f"  • جدیدترین: {code(str(uid))} · {code(_fmt_ts(ts))}")
        else:
            lines.append("  • جدیدترین: —")

    text = "\n".join(lines)
    msg, entities = CustomMarkdown.parse(text)
    return msg, entities


def _ranked_table(title: str, headers: list[str], rows: list[list[str]], empty_text: str) -> types.PageBlockTable:
    header_row = types.PageTableRow(cells=[types.PageTableCell(text=_rt(h), header=True) for h in headers])
    if not rows:
        body = [types.PageTableRow(cells=[types.PageTableCell(text=_rt(empty_text), colspan=len(headers))])]
    else:
        body = [types.PageTableRow(cells=[types.PageTableCell(text=_rt(c)) for c in row]) for row in rows]
    return types.PageBlockTable(title=_rt(title), bordered=True, compact=True, rows=[header_row, *body])


def _spend_table(
    top: list[tuple[int | None, int, int]], title: str, empty_text: str = "داده‌ای موجود نیست"
) -> types.PageBlockTable:
    rows = [
        [_MEDALS.get(i, f"{i}."), str(uid) if uid is not None else "?", f"{total:,} تومان", f"{cnt}"]
        for i, (uid, total, cnt) in enumerate(top, 1)
    ]
    return _ranked_table(title, ["#", "کاربر", "مبلغ", "شارژ"], rows, empty_text)


def _recharge_table(
    top: list[tuple[int | None, int, int]], title: str, empty_text: str = "داده‌ای موجود نیست"
) -> types.PageBlockTable:
    rows = [
        [_MEDALS.get(i, f"{i}."), str(uid) if uid is not None else "?", f"{cnt}", f"{total:,} تومان"]
        for i, (uid, cnt, total) in enumerate(top, 1)
    ]
    return _ranked_table(title, ["#", "کاربر", "شارژ", "مبلغ"], rows, empty_text)


def _config_table(
    top: list[tuple[int | None, int]], title: str, empty_text: str = "داده‌ای موجود نیست"
) -> types.PageBlockTable:
    rows = [
        [_MEDALS.get(i, f"{i}."), str(uid) if uid is not None else "?", f"{cnt}"] for i, (uid, cnt) in enumerate(top, 1)
    ]
    return _ranked_table(title, ["#", "کاربر", "کانفیگ"], rows, empty_text)


def _most_today_table(most_today: tuple[int, int] | None) -> types.PageBlockTable:
    rows = [[str(most_today[0]), f"{most_today[1]:,} تومان"]] if most_today else []
    return _ranked_table("👑 بیشترین خرید امروز", ["کاربر", "مبلغ"], rows, "هنوز خریدی ثبت نشده")


def _records_table(oldest: tuple[int, int] | None, newest: tuple[int, int] | None) -> types.PageBlockTable:
    def _row(label: str, record: tuple[int, int] | None) -> list[str]:
        if not record:
            return [label, "—", "—"]
        uid, ts = record
        return [label, str(uid), _fmt_ts(ts)]

    rows = [_row("قدیمی‌ترین", oldest), _row("جدیدترین", newest)]
    return _ranked_table("📌 سوابق", ["نوع", "کاربر", "تاریخ"], rows, "—")


def top_view_button_rows(active: str) -> list[types.PageBlockButtonRow]:
    """Native Bot API 10.3 'Button Revolution' tab selector + back, replacing the plain inline keyboard."""
    tab_buttons = [
        types.PageButton(
            text=_rt(f"• {label}" if key == active else label),
            type=types.InlineButtonTypeCallback(data=f"stats:top:{key}".encode()),
            style=types.RichButtonStyle(bg_primary=True) if key == active else None,
        )
        for key, label in _TOP_VIEWS
    ]
    back_button = types.PageButton(text=_rt("🔙 بازگشت"), type=types.InlineButtonTypeCallback(data=b"stats:main"))
    return [
        types.PageBlockButtonRow(buttons=tab_buttons),
        types.PageBlockDivider(),
        types.PageBlockButtonRow(buttons=[back_button]),
    ]


async def top_customers_rich_blocks(view: str = "today") -> list:
    """Native Bot API 10.3 rich message blocks for stats:top (tables + in-body tab buttons)."""
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    today_ts = int(today_start.timestamp())

    heading = {
        "spend": "🏆 برترین مشتریان — مبلغ خرید کل",
        "recharge": "🏆 برترین مشتریان — تعداد شارژ",
        "config": "🏆 برترین مشتریان — تعداد کانفیگ",
    }.get(view, "🏆 برترین‌های امروز")

    blocks: list = [types.PageBlockParagraph(_rt_bold(heading)), types.PageBlockDivider()]

    if view == "spend":
        top = await tx_crud.get_top_customers_by_spend(10)
        blocks.append(_spend_table(top, "💰 مبلغ خرید کل"))

    elif view == "recharge":
        top = await tx_crud.get_top_customers_by_tx_count(10)
        blocks.append(_recharge_table(top, "🔢 تعداد شارژ"))

    elif view == "config":
        top = await service_crud.get_top_customers_by_config_count(10)
        blocks.append(_config_table(top, "📦 تعداد کانفیگ"))

    else:
        (
            top_spenders,
            top_recharge,
            config_stats,
            most_today,
            oldest,
            newest,
        ) = await asyncio.gather(
            tx_crud.get_top_spenders_today(today_ts, 5),
            tx_crud.get_top_recharge_today(today_ts, 5),
            service_crud.get_today_config_stats(today_ts, 5),
            tx_crud.get_most_spender_today(today_ts),
            tx_crud.get_oldest_customer(),
            tx_crud.get_newest_customer(),
        )

        blocks.append(_most_today_table(most_today))
        blocks.append(types.PageBlockDivider())
        blocks.append(_spend_table(top_spenders, "💰 برترین خریداران (مبلغ)"))
        blocks.append(types.PageBlockDivider())
        blocks.append(_recharge_table(top_recharge, "🔢 بیشترین شارژ (تعداد)"))
        blocks.append(types.PageBlockDivider())
        blocks.append(
            _config_table(
                config_stats["top_buyers"],
                f"📦 خرید کانفیگ — {config_stats['total_today']:,} عدد",
                empty_text="امروز کانفیگی فروخته نشده",
            )
        )
        blocks.append(types.PageBlockDivider())
        blocks.append(_records_table(oldest, newest))

    blocks.append(types.PageBlockDivider())
    blocks.extend(top_view_button_rows(view))
    blocks.append(types.PageBlockDivider())
    blocks.append(types.PageBlockFooter(_rt("Coded By @AmirKenzoo")))
    return blocks
