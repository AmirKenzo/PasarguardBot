import asyncio
import html
import time

from app.db.crud.panels import PanelsManager
from app.logger import LogTag, LogType, get_logger
from app.services.panels.auth import (
    format_panel_refresh_status,
    panel_needs_cookie_refresh,
    refresh_panel_cookie,
)
from app.services.panels.cookies import format_panel_cookie_validity
from app.telegram.shared.utils.logging import send_log_message

logger = get_logger(__name__)

_COOKIE_REFRESH_CONCURRENCY = 5


def _build_cookie_update_log(
    *,
    successful_panels: list[tuple[str, str]],
    failed_panels: list[tuple[str, str, str]],
    skipped_panels: list[tuple[str, str]],
    elapsed: float,
) -> str:
    total = len(successful_panels) + len(failed_panels) + len(skipped_panels)
    success_count = len(successful_panels)
    failed_count = len(failed_panels)
    skipped_count = len(skipped_panels)

    parts = ["<b>🔄 به‌روزرسانی کوکی پنل‌ها</b>\n\n"]

    if failed_count == 0 and success_count > 0:
        parts.append(f"✅ <b>همه پنل‌های نیازمند با موفقیت به‌روزرسانی شدند</b> ({success_count}/{total})\n\n")
    elif failed_count > 0 or success_count > 0:
        parts.append(
            f"📊 <b>نتیجه:</b> {success_count} موفق، {failed_count} ناموفق، {skipped_count} بدون نیاز (از {total})\n\n"
        )

    if successful_panels:
        parts.append("✅ <b>موفق:</b>\n")
        for name, cookie in successful_panels:
            validity = format_panel_cookie_validity(cookie, locale="fa")
            parts.append(f"  • {html.escape(name)} — <i>{html.escape(validity)}</i>\n")

    if failed_panels:
        if successful_panels:
            parts.append("\n")
        parts.append("❌ <b>ناموفق:</b>\n")
        for name, ip, error in failed_panels:
            parts.append(f"  • {html.escape(name)} (<code>{html.escape(ip)}</code>)\n")
            parts.append(f"    └ <i>{html.escape(error)}</i>\n")

    if skipped_panels:
        if successful_panels or failed_panels:
            parts.append("\n")
        parts.append("⏭ <b>بدون نیاز به به‌روزرسانی:</b>\n")
        for name, status in skipped_panels:
            parts.append(f"  • {html.escape(name)} — <i>{html.escape(status)}</i>\n")

    parts.append(f"\n⏱ زمان: {elapsed:.1f}s")
    return "".join(parts)


async def get_cookies():
    start_time = time.time()
    logger.debug("%s get_cookies started", LogTag.JOB)

    panels = await PanelsManager().get_all_panels()
    if not panels:
        await send_log_message(LogType.OTHER, message="❌ هیچ پنلی برای به‌روزرسانی کوکی یافت نشد.")
        logger.debug("%s get_cookies completed: 0 panels found", LogTag.JOB)
        return

    logger.debug(f"{LogTag.JOB} get_cookies: Processing {len(panels)} panels")
    successful_panels: list[tuple[str, str]] = []
    failed_panels: list[tuple[str, str, str]] = []
    skipped_panels: list[tuple[str, str]] = []
    panels_log_summary: list[tuple[int, str]] = []

    to_refresh = []
    for panel in panels:
        if not panel_needs_cookie_refresh(panel):
            status = format_panel_refresh_status(panel, locale="en")
            skipped_panels.append((panel.name, format_panel_refresh_status(panel, locale="fa")))
            panels_log_summary.append((panel.code, status))
            logger.debug("%s get_cookies: skipped %s — %s", LogTag.JOB, panel.code, status)
            continue
        to_refresh.append(panel)

    sem = asyncio.Semaphore(_COOKIE_REFRESH_CONCURRENCY)

    async def _refresh_one(panel):
        async with sem:
            try:
                token = await refresh_panel_cookie(panel)
                status = format_panel_cookie_validity(token, locale="en")
                return ("ok", panel, token, status)
            except Exception as e:
                return ("fail", panel, e, None)

    results = await asyncio.gather(*[_refresh_one(p) for p in to_refresh]) if to_refresh else []
    for kind, panel, payload, status in results:
        if kind == "ok":
            successful_panels.append((panel.name, payload))
            panels_log_summary.append((panel.code, status))
            logger.debug("%s get_cookies: refreshed %s — %s", LogTag.JOB, panel.code, status)
        else:
            failed_panels.append((panel.name, panel.base_url, str(payload)))
            logger.error(f"{LogTag.JOB} get_cookies failed for panel {panel.name}: {payload}")

    elapsed = time.time() - start_time
    if successful_panels or failed_panels:
        await send_log_message(
            LogType.OTHER,
            message=_build_cookie_update_log(
                successful_panels=successful_panels,
                failed_panels=failed_panels,
                skipped_panels=skipped_panels,
                elapsed=elapsed,
            ),
            parse_mode="html",
        )

    panels_summary = ", ".join(f"{panel_code}: {status}" for panel_code, status in panels_log_summary)
    logger.info(
        f"{LogTag.JOB} get_cookies | duration={elapsed:.2f}s, "
        f"ok={len(successful_panels)}, fail={len(failed_panels)}, skip={len(skipped_panels)}"
        + (f" | {panels_summary}" if panels_summary else "")
    )
