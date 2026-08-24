"""Service-management inline keyboard builders."""

from telethon.tl.types import KeyboardInlineButtonRow, ReplyInlineMarkup

from app.db.crud.keyboards import KeyboardButtonCRUD
from app.db.crud.panels import PanelsManager
from app.logger import get_logger
from app.services.panels.settings import (
    panel_button_enabled,
    panel_has_time_plans,
    panel_has_volume_plans,
)

from .common import (
    _get_keyboard_button_config,
    styled_callback_button,
    styled_copy_button,
    styled_webview_button,
)

logger = get_logger(__name__)


async def create_inline_service_buttons(services, panel=None, settings=None, admin=False, link=None, status=None):
    get_panel = await PanelsManager().get_panel_by_code(panel.code)
    keyboard_crud = KeyboardButtonCRUD()

    change_sub_text, change_sub_style = await _get_keyboard_button_config(
        keyboard_crud, "in.ms.change_sub", "🔗 تغییر ساب"
    )
    change_link_text, change_link_style = await _get_keyboard_button_config(
        keyboard_crud, "in.ms.change_link", "🔗 تغییر لینک"
    )
    copy_link_text, copy_link_style = await _get_keyboard_button_config(keyboard_crud, "in.ms.copy_link", "🔗 کپی لینک")
    info_text, info_style = await _get_keyboard_button_config(keyboard_crud, "in.ms.info", "⚙️ نمایش اطلاعات بیشتر")
    extra_volume_text, extra_volume_style = await _get_keyboard_button_config(
        keyboard_crud, "in.ms.extra_volume", "♾️ حجم اضافه"
    )
    extend_time_text, extend_time_style = await _get_keyboard_button_config(
        keyboard_crud, "in.ms.extend_time", "📅 تمدید زمان"
    )
    extend_service_text, extend_service_style = await _get_keyboard_button_config(
        keyboard_crud, "in.ms.extend_service", "💎 تمدیدسرویس"
    )
    qrcode_text, qrcode_style = await _get_keyboard_button_config(keyboard_crud, "in.ms.qrcode", "🔘 دریافت Qrcode")
    transfer_config_text, transfer_config_style = await _get_keyboard_button_config(
        keyboard_crud, "in.ms.transfer_config", "🔎 واگذاری کانفیگ"
    )
    other_links_text, other_links_style = await _get_keyboard_button_config(
        keyboard_crud, "in.ms.other_links", "➕ نمایش لینک‌های دیگر"
    )
    show_clients_text, show_clients_style = await _get_keyboard_button_config(
        keyboard_crud, "in.ms.show_clients", "🖥 نمایش کلاینت‌ها"
    )
    usage_chart_text, usage_chart_style = await _get_keyboard_button_config(
        keyboard_crud, "in.ms.usage_chart", "📊 نمودار مصرف"
    )
    delete_service_text, delete_service_style = await _get_keyboard_button_config(
        keyboard_crud, "in.ms.delete_service", "🗑 حذف این کانفیگ برای همیشه"
    )
    back_to_services_text, back_to_services_style = await _get_keyboard_button_config(
        keyboard_crud, "in.ms.back_to_services", "بازگشت به لیست سرویس‌ها"
    )

    change_sub = styled_callback_button(change_sub_text, f"ChangeSub:{panel.code}:{services.code}", change_sub_style)
    change_link = styled_callback_button(
        change_link_text, f"ChangeLink:{panel.code}:{services.code}", change_link_style
    )
    web = styled_webview_button(info_text, f"{link}", info_style)
    copy_link = styled_copy_button(copy_link_text, f"{link}", copy_link_style)

    is_fair_usage_plan = False
    if services.package_size and panel:
        from app.db.crud.plans import PlanManager

        plan = await PlanManager().get_plan_by_volume_for_display(
            gb=services.package_size / (1024**3),
            panel_code=panel.code,
        )
        if plan and hasattr(plan, "plan_type") and plan.plan_type in ["fair_usage", "fair"]:
            is_fair_usage_plan = True

    is_test_service = getattr(services, "is_test", False) is True

    active_buttons = []
    if admin:
        if not is_test_service:
            if not is_fair_usage_plan and panel_has_volume_plans(get_panel):
                active_buttons.append(
                    styled_callback_button(extra_volume_text, f"KharidSize:{services.code}", extra_volume_style)
                )
            if panel_has_time_plans(get_panel):
                active_buttons.append(
                    styled_callback_button(extend_time_text, f"KharidZaman:{services.code}", extend_time_style)
                )
            active_buttons.append(
                styled_callback_button(extend_service_text, f"TamdidVPN_{services.code}", extend_service_style)
            )
        active_buttons.extend(
            [
                styled_callback_button(qrcode_text, f"getQrcode:{services.code}", qrcode_style),
                styled_callback_button(transfer_config_text, f"TransferConfig:{services.code}", transfer_config_style),
                styled_callback_button(other_links_text, f"othersSubLinks:{services.code}", other_links_style),
                styled_callback_button(show_clients_text, f"showClients:{services.code}", show_clients_style),
                styled_callback_button(usage_chart_text, f"UsageChart:{services.code}:7:0", usage_chart_style),
            ]
        )
    else:
        if not is_test_service:
            if (
                settings.upg_mode
                and panel_button_enabled(get_panel, "btn_hajm")
                and not is_fair_usage_plan
                and panel_has_volume_plans(get_panel)
            ):
                active_buttons.append(
                    styled_callback_button(extra_volume_text, f"KharidSize:{services.code}", extra_volume_style)
                )
            if (
                settings.extension_mode
                and panel_button_enabled(get_panel, "btn_zaman")
                and panel_has_time_plans(get_panel)
            ):
                active_buttons.append(
                    styled_callback_button(extend_time_text, f"KharidZaman:{services.code}", extend_time_style)
                )
            if settings.tamdid_mode and panel_button_enabled(get_panel, "btn_tamdid"):
                active_buttons.append(
                    styled_callback_button(extend_service_text, f"TamdidVPN_{services.code}", extend_service_style)
                )
        if settings.qr_mode and panel_button_enabled(get_panel, "btn_qr"):
            active_buttons.append(styled_callback_button(qrcode_text, f"getQrcode:{services.code}", qrcode_style))
        if settings.transfer_config_mode and panel_button_enabled(get_panel, "btn_transfer"):
            active_buttons.append(
                styled_callback_button(transfer_config_text, f"TransferConfig:{services.code}", transfer_config_style)
            )
        if settings.other_links_mode and panel_button_enabled(get_panel, "btn_other_links"):
            active_buttons.append(
                styled_callback_button(other_links_text, f"othersSubLinks:{services.code}", other_links_style)
            )
        if settings.client_list_mode and panel_button_enabled(get_panel, "btn_clients"):
            active_buttons.append(
                styled_callback_button(show_clients_text, f"showClients:{services.code}", show_clients_style)
            )
        if settings.usage_chart_mode and panel_button_enabled(get_panel, "btn_usage_chart"):
            active_buttons.append(
                styled_callback_button(usage_chart_text, f"UsageChart:{services.code}:7:0", usage_chart_style)
            )

    active_button_rows = [KeyboardInlineButtonRow(active_buttons[i : i + 2]) for i in range(0, len(active_buttons), 2)]

    if admin:
        admin_extra = [
            KeyboardInlineButtonRow(
                [
                    styled_callback_button("✅ فعال / ❌ غیرفعال", f"AdminConfigToggle:{services.code}"),
                ]
            ),
            KeyboardInlineButtonRow(
                [
                    styled_callback_button("📦 حجم ±", f"AdminConfigVolume:{services.code}"),
                    styled_callback_button("📅 زمان ±", f"AdminConfigTime:{services.code}"),
                ]
            ),
        ]
        back_buttons = [
            KeyboardInlineButtonRow(
                [styled_callback_button("🗑 حذف کانفیگ کاربر (سریع)", f"DeleteServiceAdmin:{services.code}")]
            ),
            KeyboardInlineButtonRow(
                [styled_callback_button("بازگشت به لیست سرویس های کاربر", f"BackToServiceListAdmin:{services.id}")]
            ),
        ]
        back_buttons = admin_extra + back_buttons
    else:
        back_buttons = []
        if (
            settings.del_service_mode
            and panel_button_enabled(get_panel, "btn_del_service")
            and status in ["disabled", "expired", "limited"]
        ):
            logger.debug(f"Delete Config User Enable For: {services.code}")
            back_buttons.append(
                KeyboardInlineButtonRow(
                    [
                        styled_callback_button(
                            delete_service_text, f"DeleteService:{services.code}", delete_service_style
                        )
                    ]
                )
            )
        back_buttons.append(
            KeyboardInlineButtonRow(
                [styled_callback_button(back_to_services_text, "BackToServiceList", back_to_services_style)]
            )
        )

    first_row_buttons = []
    if admin or (settings.change_link_mode and panel_button_enabled(get_panel, "btn_change_link")):
        first_row_buttons.append(change_link)
    if admin or (settings.sub_mode and panel_button_enabled(get_panel, "btn_change_sub")):
        first_row_buttons.append(change_sub)
    if admin or (settings.copy_link_mode and panel_button_enabled(get_panel, "btn_copy_link")):
        first_row_buttons.append(copy_link)

    rows = []
    if first_row_buttons:
        rows.append(KeyboardInlineButtonRow(first_row_buttons))
    if admin or (settings.info_mode and panel_button_enabled(get_panel, "btn_info")):
        rows.append(KeyboardInlineButtonRow([web]))

    return ReplyInlineMarkup(rows + active_button_rows + back_buttons)
