"""Support tickets: the line-per-fact card, the admin service list/detail and cache."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from telethon.errors.rpcerrorlist import MessageNotModifiedError
from telethon.extensions import html
from telethon.tl import types
from telethon.tl.custom import Message

from app.services.support import (
    PANEL_ERROR_UNREACHABLE,
    ServicesOverview,
    build_service_card,
    build_service_snapshot,
)
from app.telegram.shared import support_ticket as ticket_module
from app.telegram.shared.support_ticket import (
    FILTER_ACTIVE,
    FILTER_ALL,
    RAIL,
    ServicesListContext,
    SupportTicket,
)

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
GB = 1024**3


def _service(code: int = 1234, *, user_id: int = 555, days_left: int = 20) -> SimpleNamespace:
    return SimpleNamespace(
        code=code,
        username=f"ali_{code}",
        id=user_id,
        in_panel=7,
        panel_userid=code,
        package_size=30 * GB,
        expiration_time=int(NOW.timestamp()) + days_left * 86400,
        is_test=False,
    )


def _panel() -> SimpleNamespace:
    return SimpleNamespace(code=7, name="پنل اصلی")


def _ticket(**overrides) -> SupportTicket:
    data = {
        "user_id": 555,
        "target": "1234",
        "text": "سلام، سرویسم وصل نمی‌شود",
        "sender_name": "Ali",
        "sender_username": "ali",
        "created_at": int(NOW.timestamp()),
        "token": "0123456789",
    }
    data.update(overrides)
    return SupportTicket(**data)


def _crud(service=None, services=None):
    class _Crud:
        async def get_service(self, code):
            if service is None or str(code) != str(service.code):
                return False, "Service not found."
            return True, service

        async def get_services_reverse(self, user_id):
            return list(services or [])

    return _Crud()


def _panels():
    class _Panels:
        async def get_all_panels(self):
            return [_panel()]

    return _Panels()


def _buttons(rows) -> list[str]:
    return [button.text for row in rows for button in row]


def _data(rows) -> list[str]:
    return [button.type.data.decode() for row in rows for button in row]


def _button_by_prefix(rows, prefix: str):
    return next(button for row in rows for button in row if button.type.data.decode().startswith(prefix))


def _rail_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith(RAIL)]


def _live_snapshot(code: int, state: str, *, can_renew: bool = False, can_buy: bool = False):
    service = _service(code)
    panel_user = SimpleNamespace(
        status=state,
        expire=NOW + timedelta(days=5) if state != "expired" else NOW - timedelta(days=1),
        data_limit=30 * GB,
        used_traffic=30 * GB if state == "limited" else 5 * GB,
        online_at=NOW - timedelta(hours=1),
    )
    return build_service_snapshot(
        service,
        _panel(),
        panel_user,
        now=NOW,
        can_renew=can_renew,
        can_buy_volume=can_buy,
    )


# --------------------------------------------------------------------------- #
#  Ticket card                                                                 #
# --------------------------------------------------------------------------- #


async def test_service_ticket_is_a_line_per_fact_card(monkeypatch):
    service = _service()
    snapshot = _live_snapshot(1234, "limited")
    snapshot = build_service_snapshot(
        service,
        _panel(),
        SimpleNamespace(
            status="limited",
            expire=NOW + timedelta(days=3),
            data_limit=30 * GB,
            used_traffic=30 * GB,
            online_at=NOW - timedelta(hours=2),
        ),
        now=NOW,
    )

    async def _snapshot(*args, **kwargs):
        return snapshot

    monkeypatch.setattr(ticket_module, "ServiceCRUD", lambda: _crud(service))
    monkeypatch.setattr(ticket_module, "load_service_snapshot", _snapshot)

    text, buttons = await ticket_module.build_ticket_view(_ticket(text="<b>سلام</b>"))

    lines = _rail_lines(text)
    labels = [line.split("<b>")[1].split("</b>")[0] for line in lines]
    assert labels == [
        "نام کانفیگ",
        "کد سرویس",
        "پنل",
        "وضعیت",
        "حجم",
        "مصرف",
        "انقضا",
        "آخرین اتصال",
    ]
    assert "ali_1234" in text
    assert "پنل اصلی" in text
    assert "حجم تمام شده" in text
    # Customer text is HTML-escaped inside the quote, not interpreted.
    assert "&lt;b&gt;سلام&lt;/b&gt;" in text
    assert "تیکت پشتیبانی" in text
    assert _buttons(buttons)[0] == "📨 پاسخ به کاربر"


async def test_ticket_sender_links_to_the_profile_and_escapes_the_name():
    text, _ = await ticket_module.build_ticket_view(_ticket(target="general", sender_name="Ali <Admin>"))

    assert '<a href="tg://user?id=555"><b>Ali &lt;Admin&gt;</b></a>' in text


async def test_live_unlimited_expiry_does_not_render_a_stale_database_date(monkeypatch):
    service = _service(days_left=-1)

    async def _snapshot(*args, **kwargs):
        return build_service_snapshot(
            service,
            _panel(),
            SimpleNamespace(status="active", expire=None, data_limit=0, used_traffic=0),
            now=NOW,
        )

    monkeypatch.setattr(ticket_module, "ServiceCRUD", lambda: _crud(service))
    monkeypatch.setattr(ticket_module, "load_service_snapshot", _snapshot)

    text, _ = await ticket_module.build_ticket_view(_ticket())

    assert "🟢 فعال" in text
    assert "انقضا" not in text


async def test_ticket_never_shows_another_users_service(monkeypatch):
    foreign = _service(user_id=999)
    monkeypatch.setattr(ticket_module, "ServiceCRUD", lambda: _crud(foreign))

    text, _ = await ticket_module.build_ticket_view(_ticket())

    assert "تعلق ندارد" in text
    assert "ali_1234" not in text


async def test_ticket_with_missing_service_still_goes_out(monkeypatch):
    monkeypatch.setattr(ticket_module, "ServiceCRUD", lambda: _crud(None))

    text, _ = await ticket_module.build_ticket_view(_ticket())

    assert "پیدا نشد" in text
    assert "سلام، سرویسم وصل نمی‌شود" in text


async def test_panel_failure_is_stated_instead_of_guessed(monkeypatch):
    service = _service()
    snapshot = build_service_snapshot(service, _panel(), None, now=NOW, panel_error=PANEL_ERROR_UNREACHABLE)

    async def _snapshot(*args, **kwargs):
        return snapshot

    monkeypatch.setattr(ticket_module, "ServiceCRUD", lambda: _crud(service))
    monkeypatch.setattr(ticket_module, "load_service_snapshot", _snapshot)

    text, _ = await ticket_module.build_ticket_view(_ticket())

    assert "نامشخص" in text
    assert "در دسترس نیست" in text
    assert "باقی‌مانده" not in text


async def test_snapshot_crash_does_not_lose_the_customer_text(monkeypatch):
    service = _service()

    async def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(ticket_module, "ServiceCRUD", lambda: _crud(service))
    monkeypatch.setattr(ticket_module, "load_service_snapshot", _boom)

    text, _ = await ticket_module.build_ticket_view(_ticket(text="سلام"))

    assert "در دسترس نیست" in text
    assert "سلام" in text


async def test_general_ticket_has_no_service_card_and_no_refresh():
    text, buttons = await ticket_module.build_ticket_view(_ticket(target="general"))

    assert "سرویس مرتبط" not in text
    assert "متن مشتری" in text
    assert "🔄 به‌روزرسانی اطلاعات" not in _buttons(buttons)
    assert "📨 پاسخ به کاربر" in _buttons(buttons)


async def test_all_services_ticket_shows_a_summary_and_details_button(monkeypatch):
    overview = ServicesOverview(tuple(build_service_card(_service(code), _panel(), now=NOW) for code in (1, 2, 3)))

    async def _overview(user_id, **kwargs):
        return overview

    monkeypatch.setattr(ticket_module, "load_services_overview", _overview)

    text, buttons = await ticket_module.build_ticket_view(_ticket(target="all"))

    assert "همهٔ سرویس‌ها" in text
    assert "تعداد کل</b> · 3" in text
    assert any("جزئیات همهٔ سرویس‌ها" in label for label in _buttons(buttons))
    assert "supoth:555:0:all:0123456789" in _data(buttons)


async def test_all_services_ticket_survives_an_overview_failure(monkeypatch):
    async def _boom(user_id, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(ticket_module, "load_services_overview", _boom)

    text, _ = await ticket_module.build_ticket_view(_ticket(target="all"))

    assert "در دسترس نیست" in text


async def test_buttons_keep_the_ticket_token():
    buttons = ticket_module.ticket_buttons(_ticket())

    refresh = next(button for button in buttons[0] if button.text == "🔄 به‌روزرسانی اطلاعات")
    assert refresh.type.data == b"supref:555:1234:0123456789"
    assert "supoth:555:0:1234:0123456789" in _data(buttons)
    assert "bansup_555" in _data(buttons)


def test_longest_ticket_callback_fits_telegrams_limit():
    ticket = _ticket(user_id=9_999_999_999_999_999_999, target="9" * 19, token="a" * 10)

    for row in ticket_module.ticket_buttons(ticket):
        for button in row:
            assert len(button.type.data) <= 64


# --------------------------------------------------------------------------- #
#  Cache                                                                       #
# --------------------------------------------------------------------------- #


async def test_ticket_cache_roundtrip_by_token(monkeypatch):
    store: dict[str, str] = {}

    async def _set(key, value, ttl_seconds=0):
        store[key] = value

    async def _get(key):
        return store.get(key)

    monkeypatch.setattr(ticket_module, "set_app_cache", _set)
    monkeypatch.setattr(ticket_module, "get_app_cache", _get)

    ticket = _ticket()
    await ticket_module.remember_ticket(ticket)

    assert await ticket_module.recall_ticket(ticket.token) == ticket
    assert await ticket_module.recall_ticket("other-token") is None


async def test_list_context_roundtrip(monkeypatch):
    store: dict[str, str] = {}

    async def _set(key, value, ttl_seconds=0):
        store[key] = value

    async def _get(key):
        return store.get(key)

    monkeypatch.setattr(ticket_module, "set_app_cache", _set)
    monkeypatch.setattr(ticket_module, "get_app_cache", _get)

    context = ServicesListContext(user_id=555, target="1234", filter=FILTER_ACTIVE, page=2, sender_name="Ali")
    await ticket_module.remember_list_context("ctx", context)

    assert await ticket_module.recall_list_context("ctx") == context
    assert await ticket_module.recall_list_context("nope") is None


async def test_broken_cache_entry_is_ignored(monkeypatch):
    async def _get(key):
        return "{not json"

    monkeypatch.setattr(ticket_module, "get_app_cache", _get)

    assert await ticket_module.recall_ticket("0123456789") is None
    assert await ticket_module.recall_list_context("ctx") is None


# --------------------------------------------------------------------------- #
#  Admin: services list and detail                                             #
# --------------------------------------------------------------------------- #


async def test_admin_list_is_status_coloured_and_skips_the_ticket_service(monkeypatch):
    services = [_service(1), _service(2, days_left=-2), _service(3)]
    monkeypatch.setattr(ticket_module, "ServiceCRUD", lambda: _crud(services=services))
    monkeypatch.setattr(ticket_module, "PanelsManager", _panels)

    async def _states(chunk, **kwargs):
        live = []
        for service in chunk:
            code = int(service.code)
            state = "expired" if code == 2 else ("limited" if code == 3 else "active")
            live.append(_live_snapshot(code, state))
        return live

    monkeypatch.setattr(ticket_module, "load_service_states", _states)

    text, rows = await ticket_module.build_admin_services_list(
        "ctx", ServicesListContext(user_id=555, target="1", filter=FILTER_ALL, page=1), now=NOW
    )

    labels = _buttons(rows)
    assert "ali_1" not in text  # the ticket's own service is not listed
    assert "ali_2" in " ".join(labels)
    assert "ali_3" in " ".join(labels)
    service_buttons = [button for row in rows for button in row if button.type.data.decode().startswith("supd:")]
    assert len(service_buttons) == 2
    styles = [button.style for button in service_buttons]
    assert styles[0].bg_danger is True  # expired
    assert styles[1].bg_danger is True  # limited live
    assert all(button.type.data.decode().startswith("supd:ctx:") for button in service_buttons)


async def test_admin_list_filter_active_hides_expired_services(monkeypatch):
    services = [_service(1), _service(2, days_left=-2), _service(3)]
    monkeypatch.setattr(ticket_module, "ServiceCRUD", lambda: _crud(services=services))
    monkeypatch.setattr(ticket_module, "PanelsManager", _panels)

    async def _states(chunk, **kwargs):
        return [build_service_card(service, _panel(), now=NOW) for service in chunk]

    monkeypatch.setattr(ticket_module, "load_service_states", _states)

    text, rows = await ticket_module.build_admin_services_list(
        "ctx", ServicesListContext(user_id=555, target="99", filter=FILTER_ACTIVE, page=1), now=NOW
    )

    labels = " ".join(_buttons(rows))
    assert "ali_1" in labels
    assert "ali_3" in labels
    assert "ali_2" not in labels  # stored expiry is passed
    assert "فیلتر: <b>فقط فعال</b>" in text
    active_filter = next(button for row in rows for button in row if button.text == "فقط فعال")
    assert active_filter.style.bg_primary is True


async def test_admin_list_paginates(monkeypatch):
    services = [_service(code) for code in range(1, 8)]
    monkeypatch.setattr(ticket_module, "ServiceCRUD", lambda: _crud(services=services))
    monkeypatch.setattr(ticket_module, "PanelsManager", _panels)

    async def _states(chunk, **kwargs):
        return [build_service_card(service, _panel(), now=NOW) for service in chunk]

    monkeypatch.setattr(ticket_module, "load_service_states", _states)

    _, first_rows = await ticket_module.build_admin_services_list(
        "ctx", ServicesListContext(user_id=555, target="99", filter=FILTER_ALL, page=1), now=NOW
    )
    first_service_buttons = [b for row in first_rows for b in row if b.type.data.decode().startswith("supd:")]
    assert len(first_service_buttons) == 5
    assert "supl:ctx:all:2" in _data(first_rows)

    _, second_rows = await ticket_module.build_admin_services_list(
        "ctx", ServicesListContext(user_id=555, target="99", filter=FILTER_ALL, page=2), now=NOW
    )
    second_service_buttons = [b for row in second_rows for b in row if b.type.data.decode().startswith("supd:")]
    assert len(second_service_buttons) == 2
    assert "supl:ctx:all:1" in _data(second_rows)


async def test_admin_list_with_no_match_keeps_the_filter(monkeypatch):
    services = [_service(2, days_left=-2)]
    monkeypatch.setattr(ticket_module, "ServiceCRUD", lambda: _crud(services=services))
    monkeypatch.setattr(ticket_module, "PanelsManager", _panels)

    async def _states(chunk, **kwargs):
        return [build_service_card(service, _panel(), now=NOW) for service in chunk]

    monkeypatch.setattr(ticket_module, "load_service_states", _states)

    text, rows = await ticket_module.build_admin_services_list(
        "ctx", ServicesListContext(user_id=555, target="99", filter=FILTER_ACTIVE, page=1), now=NOW
    )

    assert "سرویسی با این فیلتر پیدا نشد" in text
    assert "supl:ctx:all:1" in _data(rows)


async def test_admin_detail_shows_the_service_and_a_back_button(monkeypatch):
    service = _service(1234)
    snapshot = _live_snapshot(1234, "active")

    async def _snapshot(*args, **kwargs):
        return snapshot

    monkeypatch.setattr(ticket_module, "ServiceCRUD", lambda: _crud(service))
    monkeypatch.setattr(ticket_module, "load_service_snapshot", _snapshot)

    card = await ticket_module.load_service_card(555, "1234")
    text, rows = ticket_module.build_admin_service_detail("ctx", 1234, card)

    assert "مشخصات سرویس" in text
    assert "ali_1234" in text
    assert "وضعیت" in text
    back = _button_by_prefix(rows, "supb:")
    assert back.text == "🔙 بازگشت به لیست"
    assert back.type.data == b"supb:ctx"


async def test_admin_detail_rejects_a_foreign_service(monkeypatch):
    foreign = _service(1234, user_id=999)
    monkeypatch.setattr(ticket_module, "ServiceCRUD", lambda: _crud(foreign))

    card = await ticket_module.load_service_card(555, "1234")
    text, _ = ticket_module.build_admin_service_detail("ctx", 1234, card)

    assert "تعلق ندارد" in text


# --------------------------------------------------------------------------- #
#  Rich admin list/detail (buttons inside the message)                         #
# --------------------------------------------------------------------------- #


def _button_rows(blocks) -> list[types.PageBlockButtonRow]:
    return [block for block in blocks if isinstance(block, types.PageBlockButtonRow)]


def _cell_text(cell: types.PageTableCell) -> str:
    value = cell.text
    while not isinstance(value, str) and hasattr(value, "text"):
        value = value.text
    return str(value)


def _row_labels(row: types.PageBlockButtonRow) -> list[str]:
    return [button.text.text for button in row.buttons]


def _row_data(row: types.PageBlockButtonRow) -> list[str]:
    return [button.type.data.decode() for button in row.buttons]


async def test_rich_detail_has_table_and_back_button_inside(monkeypatch):
    service = _service(1234)
    snapshot = _live_snapshot(1234, "active")

    async def _snapshot(*args, **kwargs):
        return snapshot

    monkeypatch.setattr(ticket_module, "ServiceCRUD", lambda: _crud(service))
    monkeypatch.setattr(ticket_module, "load_service_snapshot", _snapshot)

    card = await ticket_module.load_service_card(555, "1234")
    blocks = ticket_module.build_admin_service_detail_rich("ctx", 1234, card)

    table = next(block for block in blocks if isinstance(block, types.PageBlockTable))
    labels = [_cell_text(row.cells[0]) for row in table.rows]
    assert labels[:3] == ["نام کانفیگ", "کد سرویس", "پنل"]
    assert "وضعیت" in labels

    back_row = next(row for row in _button_rows(blocks) if _row_labels(row) == ["🔙 بازگشت به لیست"])
    assert _row_data(back_row) == ["supb:ctx"]
    assert not any(isinstance(block, types.PageBlockKicker) for block in blocks)


async def test_unchanged_services_list_does_not_send_a_duplicate(monkeypatch):
    from app.telegram.admin import support as admin_support

    async def _list(*args):
        return "unchanged list", []

    monkeypatch.setattr(admin_support, "_safe_list", _list)
    responses = []

    class _Event:
        async def edit(self, *args, **kwargs):
            raise MessageNotModifiedError(request=None)

        async def respond(self, *args, **kwargs):
            responses.append(args)

    await admin_support._edit_services_list(_Event(), "ctx", ServicesListContext(user_id=555))

    assert responses == []


async def test_send_services_list_stays_an_inline_keyboard(monkeypatch):
    from app.telegram.admin import support as admin_support

    async def _html(*args, **kwargs):
        return "html body", [[types.KeyboardInlineButton("inline", types.InlineButtonTypeCallback(b"x"))]]

    monkeypatch.setattr(admin_support, "_safe_list", _html)

    class _Event:
        chat_id = 1
        sender_id = 1

        def __init__(self):
            self.responded = None

        async def respond(self, text=None, buttons=None, **kwargs):
            self.responded = (text, buttons)

    event = _Event()
    await admin_support._send_services_list(event, "ctx", ServicesListContext(user_id=555))

    assert event.responded is not None
    assert event.responded[0] == "html body"


async def test_detail_uses_the_rich_card_when_supported(monkeypatch):
    from app.telegram.admin import support as admin_support

    async def _card(*args):
        return ticket_module.ServiceCard("سرویس مرتبط", (("نام کانفیگ", "ali_1234"),))

    edited = []

    async def _rich_edit(event, blocks):
        edited.append(blocks)

    monkeypatch.setattr(admin_support, "load_service_card", _card)
    monkeypatch.setattr(admin_support, "edit_native_rich_message", _rich_edit)

    class _Event:
        async def edit(self, *args, **kwargs):
            raise AssertionError("plain edit must not be used")

    await admin_support._edit_service_detail(_Event(), "ctx", ServicesListContext(user_id=555), 1234)

    assert len(edited) == 1
    table = next(block for block in edited[0] if isinstance(block, types.PageBlockTable))
    assert _cell_text(table.rows[0].cells[1]) == "ali_1234"


async def test_rejected_rich_detail_reuses_the_snapshot_for_html(monkeypatch):
    from app.telegram.admin import support as admin_support

    lookups = []
    service = _service()

    async def _snapshot(*args, **kwargs):
        lookups.append(args)
        return _live_snapshot(1234, "active")

    async def _reject_rich(event, blocks):
        raise RuntimeError("RICH_MESSAGE_BLOCK_UNSUPPORTED")

    monkeypatch.setattr(ticket_module, "ServiceCRUD", lambda: _crud(service))
    monkeypatch.setattr(ticket_module, "load_service_snapshot", _snapshot)
    monkeypatch.setattr(admin_support, "edit_native_rich_message", _reject_rich)

    class _Event:
        def __init__(self):
            self.edited = None

        async def edit(self, text, **kwargs):
            self.edited = (text, kwargs)

    event = _Event()
    await admin_support._edit_service_detail(event, "ctx", ServicesListContext(user_id=555), 1234)

    assert len(lookups) == 1
    assert "ali_1234" in event.edited[0]
    assert _data(event.edited[1]["buttons"]) == ["supb:ctx"]


async def test_detail_falls_back_when_rich_construction_fails(monkeypatch):
    from app.telegram.admin import support as admin_support

    async def _card(*args):
        return ticket_module.ServiceCard("سرویس مرتبط", (("نام کانفیگ", "ali_1234"),))

    def _broken_rich(*args):
        raise RuntimeError("rich blocks unavailable")

    monkeypatch.setattr(admin_support, "load_service_card", _card)
    monkeypatch.setattr(admin_support, "build_admin_service_detail_rich", _broken_rich)

    class _Event:
        def __init__(self):
            self.edited = None

        async def edit(self, text=None, buttons=None, **kwargs):
            self.edited = (text, buttons)

    event = _Event()
    await admin_support._edit_service_detail(event, "ctx", ServicesListContext(user_id=555), 1234)

    assert event.edited is not None
    assert "ali_1234" in event.edited[0]
    assert _data(event.edited[1]) == ["supb:ctx"]


# --------------------------------------------------------------------------- #
#  Refresh updates the same message (even without a cache entry)               #
# --------------------------------------------------------------------------- #


HTML_TICKET = """🏷 <b>تیکت پشتیبانی</b>

<b>Ali K</b> · <code>555</code> · @ali
<code>1405/03/11 15:30:00</code>

<b>سرویس مرتبط</b>
│ <b>نام کانفیگ</b> · Ali_1
│ <b>کد سرویس</b> · 1234

<b>متن مشتری</b>
<blockquote expandable>سلام، سرویسم قطع شده.
از دیروز وصل نمی‌شه.</blockquote>"""


def _message(markup: str, *, date: datetime = NOW) -> Message:
    plain, entities = html.parse(markup)
    return Message(id=1, peer_id=types.PeerUser(1), date=date, message=plain, entities=entities)


@pytest.mark.parametrize("created_at", [int(NOW.timestamp()), 0])
async def test_expired_cache_recovery_preserves_the_original_ticket_time(created_at):
    text, _ = await ticket_module.build_ticket_view(_ticket(target="general", created_at=created_at))

    ticket = ticket_module.ticket_from_message(_message(text, date=NOW + timedelta(seconds=8)), 555, "general")

    assert ticket is not None
    assert ticket.created_at == created_at


@pytest.mark.parametrize("sender_name", ["متن مشتری", "🧑 متن مشتری <Admin>", "Ali · K\nمتن مشتری"])
async def test_expired_cache_recovery_uses_the_customer_quote(sender_name):
    customer_text = "🛠 سلام\nمتن مشتری\nمشکل هنوز هست."
    text, _ = await ticket_module.build_ticket_view(
        _ticket(target="general", sender_name=sender_name, text=customer_text)
    )
    message = _message(text)

    ticket = ticket_module.ticket_from_message(message, 555, "general")

    assert ticket is not None
    assert ticket.text == customer_text
    assert ticket.sender_name == sender_name
    assert ticket.sender_username == "ali"
    assert ticket.created_at == int(NOW.timestamp())


def test_ticket_from_message_recovers_sender_and_message():
    ticket = ticket_module.ticket_from_message(_message(HTML_TICKET), 555, "1234")

    assert ticket is not None
    assert ticket.user_id == 555
    assert ticket.target == "1234"
    assert ticket.sender_name == "Ali K"
    assert ticket.sender_username == "ali"
    assert ticket.text == "سلام، سرویسم قطع شده.\nاز دیروز وصل نمی‌شه."
    assert ticket.token


def test_ticket_recovery_rejects_missing_or_malformed_content():
    assert ticket_module.ticket_from_message(_message("سلام"), 555, "1234") is None
    assert ticket_module.ticket_from_message(None, 555, "1234") is None
    malformed = _message(HTML_TICKET.replace("1405/03/11 15:30:00", "invalid timestamp"))
    assert ticket_module.ticket_from_message(malformed, 555, "1234") is None


async def test_refresh_edits_the_original_message_without_cache(monkeypatch):
    from app.telegram.admin import support as admin_support

    async def _no_ticket(token):
        return None

    async def _view(ticket):
        return f"refreshed {ticket.target}", []

    remembered = []

    async def _remember(ticket):
        remembered.append(ticket)

    monkeypatch.setattr(admin_support, "recall_ticket", _no_ticket)
    monkeypatch.setattr(admin_support, "build_ticket_view", _view)
    monkeypatch.setattr(admin_support, "remember_ticket", _remember)

    class _Event:
        def __init__(self):
            self.edited = None
            self.responded = False
            self.answers = []

        async def get_message(self):
            return _message(HTML_TICKET)

        async def edit(self, text=None, buttons=None, **kwargs):
            self.edited = (text, buttons)

        async def respond(self, *args, **kwargs):
            self.responded = True

        async def answer(self, text=None, **kwargs):
            self.answers.append(text)

    event = _Event()
    # A legacy 3-part refresh button: no token, entry not in the cache.
    await admin_support._refresh_ticket(event, "supref:555:1234")

    assert event.edited is not None
    assert event.edited[0] == "refreshed 1234"
    assert event.responded is False
    assert remembered and remembered[0].text.startswith("سلام، سرویسم قطع شده.")
