from typing import Any
from urllib.parse import unquote

from pasarguard import ConfigFormat, PasarguardAPI

from app.logger import get_logger
from app.services.billing.renewal import require_panel_userid
from app.services.panels.settings import panel_single_config_link_indexes

logger = get_logger(__name__)

ALL_LINKS_SELECTIONS = {"*", "all", "همه"}


def parse_single_config_link_indexes(selection: str | None) -> list[int] | None:
    """Parse 1-based link indexes/ranges. Returns None when all links are selected."""
    if not selection or not selection.strip():
        return []

    indexes: set[int] = set()
    for raw_part in selection.replace("،", ",").split(","):
        part = raw_part.strip().lower()
        if not part:
            continue
        if part in ALL_LINKS_SELECTIONS:
            return None

        if "-" in part:
            start_text, end_text = [item.strip() for item in part.split("-", 1)]
            if not start_text.isdigit() or not end_text.isdigit():
                continue
            start, end = int(start_text), int(end_text)
            if start <= 0 or end <= 0:
                continue
            if start > end:
                start, end = end, start
            indexes.update(range(start - 1, end))
            continue

        if part.isdigit() and int(part) > 0:
            indexes.add(int(part) - 1)

    return sorted(indexes)


def summarize_single_config_link_selection(selection: str | None) -> str:
    if selection is None:
        return "تنظیم نشده"
    if not selection.strip():
        return "غیرفعال"
    if selection.strip().lower() in ALL_LINKS_SELECTIONS:
        return "همه لینک‌ها"
    return selection.strip()


def normalize_config_links_response(response: Any) -> list[str]:
    if response is None:
        return []
    if isinstance(response, str):
        return [line.strip() for line in response.splitlines() if line.strip()]
    if isinstance(response, dict):
        for key in ("links", "items", "data"):
            value = response.get(key)
            if value:
                return normalize_config_links_response(value)
        return []
    if isinstance(response, (list, tuple, set)):
        return [str(item).strip() for item in response if str(item).strip()]

    for attr in ("links", "items", "data"):
        value = getattr(response, attr, None)
        if value:
            return normalize_config_links_response(value)

    text = str(response).strip()
    return [text] if text else []


def format_single_config_links_for_message(links: list[str]) -> str:
    return "\n".join(f"`{link}`" for link in links)


def safe_display_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text.encode("utf-8", "surrogatepass").decode("utf-8", errors="replace")


def config_link_display_name(link: str, index: int) -> str:
    try:
        if "#" in link:
            raw = link.rsplit("#", 1)[-1]
            name = unquote(raw, errors="replace").strip()
            if name:
                return safe_display_text(name)
    except Exception:
        pass
    return f"Config {index + 1}"


async def fetch_user_config_links(panel, panel_userid: int | None) -> list[str]:
    if panel_userid is None:
        return []

    try:
        response = await PasarguardAPI(base_url=panel.base_url).get_user_subscription_by_id(
            user_id=int(panel_userid),
            client_type=ConfigFormat.LINKS,
            token=panel.cookie,
        )
    except Exception as exc:
        logger.warning("Could not fetch config links for panel=%s user=%s: %s", panel.code, panel_userid, exc)
        return []

    return normalize_config_links_response(response)


async def fetch_service_config_links(service: Any, panel: Any) -> list[str]:
    """Resolve panel user id and fetch single config links (webapp + bot)."""
    api = PasarguardAPI(panel.base_url)
    panel_userid: int | None = None

    try:
        panel_userid = int(require_panel_userid(service))
    except ValueError:
        panel_userid = None

    if panel_userid is None:
        try:
            user = await api.get_user_by_username(username=service.username, token=panel.cookie)
            if user and getattr(user, "id", None) is not None:
                panel_userid = int(user.id)
        except Exception as exc:
            logger.warning(
                "Could not resolve panel user by username panel=%s service=%s: %s",
                getattr(panel, "code", None),
                getattr(service, "code", None),
                exc,
            )

    if panel_userid is None:
        raise ValueError("آیدی کاربر پنل یافت نشد. لطفاً سینک کاربران پنل را انجام دهید.")

    links = await fetch_user_config_links(panel, panel_userid)
    if links:
        return [safe_display_text(link) for link in links if safe_display_text(link)]

    try:
        user = await api.get_user_by_id(user_id=panel_userid, token=panel.cookie)
        raw_links = getattr(user, "links", None) if user else None
        if raw_links:
            return [safe_display_text(link) for link in raw_links if safe_display_text(link)]
    except Exception as exc:
        logger.warning("Fallback user.links failed panel=%s user=%s: %s", panel.code, panel_userid, exc)

    return []


async def get_selected_single_config_links_text(panel, panel_userid: int | None) -> str:
    selection = panel_single_config_link_indexes(panel)
    selected_indexes = parse_single_config_link_indexes(selection)
    if selected_indexes == []:
        return ""
    if panel_userid is None:
        return ""

    links = await fetch_user_config_links(panel, panel_userid)
    selected_links = (
        links if selected_indexes is None else [links[index] for index in selected_indexes if index < len(links)]
    )
    return format_single_config_links_for_message(selected_links)
