"""Support user flow: routing, ownership, native button styles and status wording."""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from telethon.events import StopPropagation

from app.services.support import (
    PANEL_ERROR_UNREACHABLE,
    STATE_ACTIVE,
    STATE_DISABLED,
    STATE_EXPIRED,
    STATE_EXPIRED_LIMITED,
    STATE_LIMITED,
    STATE_UNKNOWN,
    build_service_card,
    build_service_snapshot,
)
from app.telegram.keyboards.common import build_telegram_button_style, styled_callback_button
from app.telegram.keyboards.home import home_back_button
from app.telegram.shared.support_ticket import SupportTicket, ticket_buttons as build_ticket_buttons
from app.telegram.user import support as user_support

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
GB = 1024**3


def _service(code: int = 1234, user_id: int = 555) -> SimpleNamespace:
    return SimpleNamespace(
        code=code,
        username="ali_1",
        id=user_id,
        in_panel=7,
        panel_userid=99,
        package_size=30 * GB,
        expiration_time=int(NOW.timestamp()) + 20 * 86400,
        is_test=False,
    )


def _panel() -> SimpleNamespace:
    return SimpleNamespace(code=7, name="پنل اصلی")


def _snapshot(**panel_user_overrides):
    panel_user = {
        "status": "active",
        "expire": NOW + timedelta(days=20),
        "data_limit": 30 * GB,
        "used_traffic": 10 * GB,
        "online_at": NOW - timedelta(hours=2),
    }
    panel_user.update(panel_user_overrides)
    return build_service_snapshot(
        _service(),
        _panel(),
        SimpleNamespace(**panel_user),
        now=NOW,
        can_renew=True,
        can_buy_volume=True,
    )


def _data(button) -> str:
    return button.type.data.decode()


# --------------------------------------------------------------------------- #
#  Routing                                                                     #
# --------------------------------------------------------------------------- #


async def test_every_support_callback_is_routed_here():
    samples = [
        user_support.CB_ALL,
        user_support.CB_GENERAL,
        user_support.CB_BACK,
        "sup:pick:2",
        "sup:svc:1234",
        "sup:cont:all",
        "sup:report:1234",
    ]

    for data in samples:
        event = SimpleNamespace(data=data.encode())
        assert await user_support.support_callback_filter(event), data


def test_support_callbacks_do_not_collide_with_service_callbacks():
    from app.telegram.user.services.helpers import SERVICE_CALLBACK_PREFIXES

    samples = [
        user_support.CB_ALL,
        user_support.CB_GENERAL,
        user_support.CB_BACK,
        "sup:pick:2",
        "sup:svc:1234",
        "sup:cont:1234",
        "sup:report:1234",
    ]

    for data in samples:
        assert not any(data.startswith(prefix) for prefix in SERVICE_CALLBACK_PREFIXES), data


def test_admin_ticket_callbacks_reach_the_admin_handler():
    from app.telegram.admin.support import CALLBACK_PREFIXES

    for data in (
        "supref:555:1234:0123456789",
        "supref:555:all:0123456789",
        "supoth:555:0:1234:0123456789",
        "supl:ctx123:active:2",
        "supd:ctx123:1234",
        "supb:ctx123",
    ):
        assert data.startswith(CALLBACK_PREFIXES), data


def test_longest_callback_data_fits_telegrams_limit():
    ticket = SupportTicket(user_id=9_999_999_999_999_999_999, target="9" * 19, text="x")

    for row in build_ticket_buttons(ticket):
        for button in row:
            assert len(button.type.data) <= 64, _data(button)

    assert len(user_support.CB_REPORT.encode() + b"9" * 19) <= 64


# --------------------------------------------------------------------------- #
#  Ownership                                                                   #
# --------------------------------------------------------------------------- #


def _crud(service):
    class _Crud:
        async def get_service(self, code):
            if service is None or str(code) != str(service.code):
                return False, "Service not found."
            return True, service

    return _Crud()


async def test_only_the_owner_can_open_a_service(monkeypatch):
    service = _service(user_id=555)
    monkeypatch.setattr(user_support, "ServiceCRUD", lambda: _crud(service))

    assert await user_support._owned_service(555, 1234) is service
    assert await user_support._owned_service(556, 1234) is None
    assert await user_support._owned_service(555, 999999) is None


async def test_foreign_service_falls_back_to_general_target(monkeypatch):
    service = _service(user_id=555)
    monkeypatch.setattr(user_support, "ServiceCRUD", lambda: _crud(service))

    assert await user_support._normalized_target(555, "all") == ("all", None)
    assert await user_support._normalized_target(555, None) == ("general", None)
    assert await user_support._normalized_target(555, "general") == ("general", None)

    target, resolved = await user_support._normalized_target(555, "1234")
    assert (target, resolved) is not None
    assert target == "1234"
    assert resolved is service

    assert await user_support._normalized_target(556, "1234") == ("general", None)
    assert await user_support._normalized_target(555, "999999") == ("general", None)


# --------------------------------------------------------------------------- #
#  Message filter                                                              #
# --------------------------------------------------------------------------- #


async def test_text_is_accepted_only_inside_the_support_flow(monkeypatch):
    def _step(step):
        async def _get_step(user_id):
            return step

        return _get_step

    async def _button_text(key, default):
        return default

    event = SimpleNamespace(sender_id=1, message=SimpleNamespace(text="سلام، مشکلی دارم"))

    monkeypatch.setattr(user_support, "get_button_text", _button_text)

    monkeypatch.setattr(user_support, "get_step", _step("support"))
    assert await user_support.is_support_message(event) is True

    # The status screen is navigation: text there must not file a ticket.
    monkeypatch.setattr(user_support, "get_step", _step("support_status"))
    assert await user_support.is_support_message(event) is False

    monkeypatch.setattr(user_support, "get_step", _step("support_pick"))
    assert await user_support.is_support_message(event) is False

    monkeypatch.setattr(user_support, "get_step", _step("home"))
    assert await user_support.is_support_message(event) is False


async def test_menu_labels_are_not_taken_as_support_text(monkeypatch):
    def _step(step):
        async def _get_step(user_id):
            return step

        return _get_step

    async def _button_text(key, default):
        return default

    monkeypatch.setattr(user_support, "get_step", _step("support_pick"))
    monkeypatch.setattr(user_support, "get_button_text", _button_text)

    for text in ("🔑 سرویس های من", "☎️ پشتیبانی", "/start", "☎️ هر چیزی"):
        event = SimpleNamespace(sender_id=1, message=SimpleNamespace(text=text))
        assert await user_support.is_support_message(event) is False, text


# --------------------------------------------------------------------------- #
#  Status wording                                                              #
# --------------------------------------------------------------------------- #


def test_active_service_screen_shows_volume_time_and_last_connection():
    text = user_support._status_text(_snapshot())

    assert "🟢 فعال" in text
    assert "حجم باقی‌مانده" in text
    assert "انقضا" in text
    assert "آخرین اتصال" in text
    assert "سرویس شما فعال است" in text


def test_expired_service_screen_shows_the_expiry_and_takes_turns():
    text = user_support._status_text(_snapshot(status="expired"))

    assert "زمان تمام شده" in text
    assert "زمان این سرویس به پایان رسیده است" in text
    assert "تمدید سرویس" in text


def test_limited_service_screen_shows_usage_and_remaining():
    text = user_support._status_text(_snapshot(status="limited", used_traffic=30 * GB))

    assert "حجم تمام شده" in text
    assert "حجم مصرفی" in text
    assert "حجم باقی‌مانده" in text
    assert "خرید حجم" in text
    assert "تمدید سرویس" in text


def test_both_problems_are_shown_for_expired_and_limited():
    text = user_support._status_text(_snapshot(status="limited", used_traffic=30 * GB, expire=NOW - timedelta(days=1)))

    assert "زمان و حجم تمام شده" in text
    assert "هم زمان و هم حجم این سرویس تمام شده است" in text
    assert "خرید حجم" not in text
    assert "تمدید سرویس" in text


def test_disabled_service_screen_does_not_guess_the_reason():
    text = user_support._status_text(_snapshot(status="disabled"))

    assert "⛔️ غیرفعال" in text
    assert "دلیل غیرفعال شدن سرویس در اطلاعات پنل موجود نیست" in text


def test_panel_failure_screen_says_the_data_is_missing_but_keeps_support():
    snapshot = build_service_snapshot(_service(), _panel(), None, now=NOW, panel_error=PANEL_ERROR_UNREACHABLE)

    text = user_support._status_text(snapshot)

    assert snapshot.state == STATE_UNKNOWN
    assert "اطلاعات پنل" in text
    assert "در دسترس نیست" in text
    assert "می‌توانید پیام پشتیبانی بفرستید" in text


def test_near_expiry_and_low_volume_use_a_yellow_line_not_a_new_colour():
    snapshot = _snapshot(used_traffic=29 * GB, expire=NOW + timedelta(days=2))

    text = user_support._status_text(snapshot)

    assert "🟡" in text
    assert "کمتر از ۳ روز" in text
    assert "🟡" in text


# --------------------------------------------------------------------------- #
#  Native button styles                                                        #
# --------------------------------------------------------------------------- #


def test_expired_service_offers_renew_and_always_support():
    rows = user_support._status_buttons(_snapshot(status="expired"), back_data="home.back")

    renew = rows[0][0]
    assert renew.text == "🔄 تمدید سرویس"
    assert _data(renew) == "TamdidVPN_1234"
    assert renew.style.bg_primary is True

    support = rows[1][0]
    assert support.text == "📨 هنوز نیاز به پشتیبانی دارم"
    assert support.style.bg_primary is True

    general, back = rows[2]
    assert general.style is None
    assert back.style is None


def test_limited_service_offers_volume_and_renew():
    rows = user_support._status_buttons(_snapshot(status="limited", used_traffic=30 * GB), back_data="home.back")

    labels = [button.text for button in rows[0]]
    assert labels == ["🔄 تمدید سرویس", "➕ خرید حجم"]
    assert all(button.style.bg_primary is True for button in rows[0])
    assert [button.text for button in rows[1]] == ["📨 هنوز نیاز به پشتیبانی دارم"]


def test_expired_and_limited_only_suggests_renewal():
    rows = user_support._status_buttons(
        _snapshot(status="limited", used_traffic=30 * GB, expire=NOW - timedelta(days=1)),
        back_data="home.back",
    )

    assert [button.text for button in rows[0]] == ["🔄 تمدید سرویس"]


def test_buttons_are_hidden_when_the_bot_or_panel_forbids_them():
    snapshot = build_service_snapshot(
        _service(),
        _panel(),
        SimpleNamespace(
            status="expired",
            expire=NOW - timedelta(days=1),
            data_limit=30 * GB,
            used_traffic=30 * GB,
            online_at=None,
        ),
        now=NOW,
        can_renew=False,
        can_buy_volume=False,
    )

    rows = user_support._status_buttons(snapshot, back_data="home.back")

    labels = [button.text for button in rows[0]]
    assert labels == ["📨 هنوز نیاز به پشتیبانی دارم"]
    assert rows[0][0].style.bg_primary is True


def test_picker_label_shows_state_name_panel_and_code():
    card = build_service_card(_service(), _panel(), now=NOW)

    label = user_support._picker_label(card)

    assert label.startswith("🟢 فعال")
    assert "ali_1" in label
    assert "پنل اصلی" in label
    assert "کد 1234" in label
    assert len(label) <= 128


def test_expired_picker_label_is_red():
    service = _service()
    service.expiration_time = int((NOW - timedelta(days=1)).timestamp())
    card = build_service_card(service, _panel(), now=NOW)

    label = user_support._picker_label(card)

    assert label.startswith("🔴 منقضی")
    assert user_support.state_style(card.state) == "danger"


def test_home_back_button_stays_default_styled():
    button = home_back_button()

    assert button.text == "🏠 بازگشت"
    assert button.style is None


def test_state_constants_stay_in_sync_with_labels():
    # Every state the flow can produce has a label and a short status word.
    for state in (STATE_ACTIVE, STATE_EXPIRED, STATE_LIMITED, STATE_EXPIRED_LIMITED, STATE_DISABLED, STATE_UNKNOWN):
        assert user_support.state_label(state)


# --------------------------------------------------------------------------- #
#  Telegram library compatibility                                              #
# --------------------------------------------------------------------------- #


def test_project_style_helper_maps_to_native_telegram_styles():
    """The flow relies on the project helper, which must produce Telethon's native style."""
    style = build_telegram_button_style("success", None)

    assert style.to_dict()["_"] == "KeyboardButtonStyle"
    assert (style.bg_success, style.bg_primary, style.bg_danger) == (True, None, None)
    assert build_telegram_button_style("danger", None).bg_danger is True
    assert build_telegram_button_style("primary", None).bg_primary is True
    # No invented colours: anything else has no style at all.
    assert build_telegram_button_style(None, None) is None
    assert build_telegram_button_style("yellow", None) is None


def test_styled_inline_button_keeps_data_and_style():
    button = styled_callback_button("🔄 تمدید سرویس", "TamdidVPN_1234", build_telegram_button_style("primary", None))

    assert button.text == "🔄 تمدید سرویس"
    assert button.type.data == b"TamdidVPN_1234"
    assert button.style.bg_primary is True


# --------------------------------------------------------------------------- #
#  Back navigation                                                             #
# --------------------------------------------------------------------------- #


class _FakeSupportEvent:
    """Minimal callback event: answers, edits and captures the buttons."""

    def __init__(self, data: str = "", sender_id: int = 555) -> None:
        self.data = data.encode()
        self.sender_id = sender_id
        self.buttons = None
        self.text = None
        self.answers = []

    async def answer(self, text=None, **kwargs):
        self.answers.append(text)

    async def edit(self, text=None, buttons=None, **kwargs):
        self.text = text
        self.buttons = buttons

    async def respond(self, text=None, buttons=None, **kwargs):
        self.text = text
        self.buttons = buttons


def _button_data(rows, label: str) -> str | None:
    for row in rows or []:
        for button in row:
            if button.text == label:
                return button.type.data.decode()
    return None


def _store(monkeypatch):
    values: dict[str, object] = {}

    async def _set(user_id, key, value, ttl=None):
        values[key] = value

    async def _get(user_id, key):
        return values.get(key)

    async def _step(user_id, step):
        values["step"] = step

    async def _delete(user_id, key):
        values.pop(key, None)

    monkeypatch.setattr(user_support, "delete_data", _delete)
    monkeypatch.setattr(user_support, "set_data", _set)
    monkeypatch.setattr(user_support, "get_data", _get)
    monkeypatch.setattr(user_support, "set_step", _step)
    return values


@pytest.mark.parametrize(("delivered", "owner_id"), [(1, 555), (1, 999), (0, 555)])
async def test_support_delivery_revalidates_ownership_and_clears_only_after_success(monkeypatch, delivered, owner_id):
    values = _store(monkeypatch)
    values.update(
        {user_support.TARGET_KEY: "1234", user_support.ORIGIN_KEY: user_support.ORIGIN_SERVICE, "step": "support"}
    )
    tickets = []
    replies = []

    async def _send(ticket):
        tickets.append(ticket)
        return delivered

    async def _home(*args):
        return []

    monkeypatch.setattr(user_support, "ServiceCRUD", lambda: _crud(_service(user_id=owner_id)))
    monkeypatch.setattr(user_support, "send_ticket_to_admins", _send)
    monkeypatch.setattr(user_support, "bhome_buttons", _home)

    class _Event:
        sender_id = 555
        message = SimpleNamespace(text="سلام، سرویسم وصل نمی‌شود")

        async def get_sender(self):
            return SimpleNamespace(first_name="Ali", last_name="K", username="ali")

        async def reply(self, text, **kwargs):
            replies.append(text)

    if delivered:
        with pytest.raises(StopPropagation):
            await user_support.support_message.__wrapped__(_Event())
    else:
        await user_support.support_message.__wrapped__(_Event())

    assert len(tickets) == 1
    assert tickets[0].user_id == 555
    assert tickets[0].target == ("1234" if owner_id == 555 else "general")
    assert tickets[0].text == "سلام، سرویسم وصل نمی‌شود"
    assert tickets[0].sender_name == "Ali K"
    if delivered:
        assert values == {"step": "home"}
        assert "با موفقیت" in replies[0]
    else:
        assert values["step"] == "support"
        assert values[user_support.TARGET_KEY] == "1234"
        assert values[user_support.ORIGIN_KEY] == user_support.ORIGIN_SERVICE
        assert "ناموفق" in replies[0]


def _snapshot_for(service, *, now=None):
    panel_user = SimpleNamespace(
        status="active",
        expire=NOW + timedelta(days=5),
        data_limit=30 * GB,
        used_traffic=5 * GB,
        online_at=None,
    )
    return build_service_snapshot(service, SimpleNamespace(code=7, name="پنل اصلی"), panel_user, now=NOW)


def test_back_from_a_report_opened_on_the_service_page_returns_there():
    assert user_support._status_back_data(1234, 3, user_support.ORIGIN_SERVICE) == "service_info:1234"
    assert user_support._status_back_data(1234, 3, user_support.ORIGIN_PICKER) == "sup:pick:1"
    assert user_support._status_back_data(1234, 1, user_support.ORIGIN_MENU) == "home.back"
    assert user_support._status_back_data(1234, 1, user_support.ORIGIN_SERVICE) == "service_info:1234"


async def test_status_screen_keeps_its_origin_across_rerenders(monkeypatch):
    service = _service()
    _store(monkeypatch)

    async def _snapshot(*args, **kwargs):
        return _snapshot_for(service)

    monkeypatch.setattr(user_support, "load_service_snapshot", _snapshot)

    first = _FakeSupportEvent()
    await user_support._render_service_status(first, service, services_total=3, origin=user_support.ORIGIN_SERVICE)
    assert _button_data(first.buttons, "🔙 بازگشت") == "service_info:1234"

    # Coming back from the message prompt re-renders without an origin argument.
    second = _FakeSupportEvent()
    await user_support._render_service_status(second, service, services_total=3, origin=None)
    assert _button_data(second.buttons, "🔙 بازگشت") == "service_info:1234"


async def test_report_callback_records_the_service_page_origin(monkeypatch):
    service = _service()
    values = _store(monkeypatch)

    class _Crud:
        async def get_service(self, code):
            return True, service

    async def _snapshot(*args, **kwargs):
        return _snapshot_for(service)

    async def _count(user_id):
        return 3

    monkeypatch.setattr(user_support, "ServiceCRUD", lambda: _Crud())
    monkeypatch.setattr(user_support, "load_service_snapshot", _snapshot)
    monkeypatch.setattr(user_support, "_count_services", _count)

    event = _FakeSupportEvent("sup:report:1234")
    # Skip the offline middleware wrapper; it would query the settings table.
    await user_support.support_callback.__wrapped__(event)

    assert values[user_support.ORIGIN_KEY] == user_support.ORIGIN_SERVICE
    assert values[user_support.TARGET_KEY] == "1234"
    assert _button_data(event.buttons, "🔙 بازگشت") == "service_info:1234"


async def test_pending_screen_text_is_explained_not_filed(monkeypatch):
    def _step(step):
        async def _get_step(user_id):
            return step

        return _get_step

    async def _button_text(key, default):
        return default

    monkeypatch.setattr(user_support, "get_button_text", _button_text)
    event = SimpleNamespace(sender_id=1, message=SimpleNamespace(text="سلام، مشکل دارم"))

    monkeypatch.setattr(user_support, "get_step", _step("support_status"))
    assert await user_support.is_pending_support_text(event) is True
    assert await user_support.is_support_message(event) is False

    # Menu labels still reach their own handlers, not the hint.
    menu = SimpleNamespace(sender_id=1, message=SimpleNamespace(text="🔑 سرویس های من"))
    assert await user_support.is_pending_support_text(menu) is False

    replies = []

    async def _reply(text, **kwargs):
        replies.append(text)

    hint_event = SimpleNamespace(sender_id=1, reply=_reply)
    monkeypatch.setattr(user_support, "get_step", _step("support_status"))
    with contextlib.suppress(StopPropagation):
        await user_support.support_screen_text.__wrapped__(hint_event)

    assert "هنوز نیاز به پشتیبانی دارم" in replies[0]
