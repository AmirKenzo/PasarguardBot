"""The report-issue button on a service page: present, pre-selected and status-coloured."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.telegram.keyboards import services as services_keyboard

PANEL = SimpleNamespace(
    code=7,
    name="پنل اصلی",
    enable=True,
    button_settings={},
    feature_settings={},
    subscription_settings={},
    renewal_settings={},
    test_settings={},
)
SERVICE = SimpleNamespace(
    code=1234,
    username="ali_1",
    id=555,
    in_panel=7,
    package_size=30 * 1024**3,
    expiration_time=0,
    is_test=False,
)
ALL_ON = SimpleNamespace(
    upg_mode=True,
    extension_mode=True,
    tamdid_mode=True,
    qr_mode=True,
    sub_mode=True,
    other_links_mode=True,
    client_list_mode=True,
    usage_chart_mode=True,
    change_link_mode=True,
    copy_link_mode=True,
    info_mode=True,
    del_service_mode=True,
    transfer_config_mode=True,
)


@pytest.fixture(autouse=True)
def _fake_backends(monkeypatch):
    class _Buttons:
        async def get_button(self, key):
            return None

        async def get_buttons_by_keys(self, keys):
            return []

    class _Panels:
        async def get_panel_by_code(self, code=None):
            return PANEL

    class _Plans:
        async def get_plan_by_volume_for_display(self, gb=None, panel_code=None):
            return None

    monkeypatch.setattr(services_keyboard, "KeyboardButtonCRUD", lambda: _Buttons())
    monkeypatch.setattr(services_keyboard, "PanelsManager", lambda: _Panels())
    monkeypatch.setattr(services_keyboard, "PlanManager", lambda: _Plans())


def _report_button(markup):
    for row in markup.rows:
        for button in row.buttons:
            if button.text == "🛠 گزارش مشکل":
                return button
    return None


async def _markup(status):
    return await services_keyboard.create_inline_service_buttons(
        SERVICE,
        PANEL,
        ALL_ON,
        admin=False,
        link="https://example.com/sub",
        status=status,
    )


@pytest.mark.parametrize(
    ("status", "style_attr"),
    [
        ("active", "bg_success"),
        ("on_hold", "bg_success"),
        ("expired", "bg_danger"),
        ("limited", "bg_danger"),
    ],
)
async def test_report_button_mirrors_the_service_state(status: str, style_attr: str):
    button = _report_button(await _markup(status))

    assert button is not None
    assert button.type.data == b"sup:report:1234"
    assert getattr(button.style, style_attr) is True


@pytest.mark.parametrize("status", ["disabled", "weird", None])
async def test_report_button_keeps_the_default_style(status):
    button = _report_button(await _markup(status))

    assert button is not None
    assert button.type.data == b"sup:report:1234"
    assert button.style is None


async def test_admin_service_page_has_no_report_button():
    markup = await services_keyboard.create_inline_service_buttons(
        SERVICE,
        PANEL,
        ALL_ON,
        admin=True,
        link="https://example.com/sub",
        status="active",
    )

    assert _report_button(markup) is None
