from __future__ import annotations

import asyncio

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select

from app.db.base import AsyncSessionLocal as Session
from app.db.models.keyboards import KeyboardButton
from app.utils.text.glass import unglass_text

# Rarely-changing config table — load once into process memory.
_buttons_by_key: dict[str, KeyboardButton] | None = None
_buttons_lock = asyncio.Lock()


def invalidate_keyboard_button_cache() -> None:
    global _buttons_by_key
    _buttons_by_key = None


async def _ensure_keyboard_button_cache() -> dict[str, KeyboardButton]:
    global _buttons_by_key
    if _buttons_by_key is not None:
        return _buttons_by_key
    async with _buttons_lock:
        if _buttons_by_key is not None:
            return _buttons_by_key
        try:
            async with Session() as session:
                result = await session.execute(select(KeyboardButton))
                rows = list(result.scalars().all())
                _buttons_by_key = {row.button_key: row for row in rows}
        except SQLAlchemyError:
            _buttons_by_key = {}
        return _buttons_by_key


class KeyboardButtonCRUD:
    async def get_button_text(self, button_key: str) -> str | None:
        button = await self.get_button(button_key)
        return button.button_text if button else None

    async def get_button(self, button_key: str) -> KeyboardButton | None:
        cache = await _ensure_keyboard_button_cache()
        return cache.get(button_key)

    async def get_buttons_by_keys(self, keys: list[str]) -> dict[str, KeyboardButton]:
        cache = await _ensure_keyboard_button_cache()
        return {key: cache[key] for key in keys if key in cache}

    async def set_button(
        self,
        button_key: str,
        *,
        button_text: str | None = None,
        description: str | None = None,
        button_style: str | None = None,
        button_icon: int | None = None,
        clear_icon: bool = False,
    ) -> bool:

        try:
            async with Session() as session:
                stmt = select(KeyboardButton).where(KeyboardButton.button_key == button_key)
                result = await session.execute(stmt)
                existing = result.scalars().first()
                if existing:
                    if button_text is not None:
                        existing.button_text = button_text
                    if description is not None:
                        existing.description = description
                    if button_style is not None:
                        existing.button_style = button_style.strip()
                    if clear_icon or button_icon is not None:
                        existing.button_icon = None if clear_icon else button_icon
                else:
                    # button_text is NOT NULL in the DB; fall back to "" (treated as
                    # "unset" everywhere text is read) so style/icon can be saved
                    # even before the admin has customized the button's text.
                    session.add(
                        KeyboardButton(
                            button_key=button_key,
                            button_text=button_text or "",
                            description=description,
                            button_style=button_style.strip() if button_style is not None else None,
                            button_icon=button_icon,
                        )
                    )
                await session.commit()
                invalidate_keyboard_button_cache()
                return True
        except SQLAlchemyError:
            return False

    async def set_button_text(self, button_key: str, button_text: str, description: str | None = None) -> bool:

        return await self.set_button(button_key, button_text=button_text, description=description)

    async def get_all(self) -> list[KeyboardButton]:
        cache = await _ensure_keyboard_button_cache()
        return list(cache.values())

    async def get_home_layout(self) -> dict[str, tuple[int, int]]:
        """Return ``{button_key: (row, order)}`` for buttons placed by the admin."""
        cache = await _ensure_keyboard_button_cache()
        return {
            key: (int(button.sort_row), int(button.sort_order or 0))
            for key, button in cache.items()
            if button.sort_row is not None
        }

    async def get_hidden_keys(self) -> set[str]:
        """Return the keys the admin switched off."""
        cache = await _ensure_keyboard_button_cache()
        return {key for key, button in cache.items() if getattr(button, "hidden", False)}

    async def set_home_layout(
        self,
        layout: dict[str, tuple[int, int]],
        hidden: set[str] | None = None,
    ) -> bool:
        """Replace the home menu layout. An empty mapping restores the default.

        ``hidden`` is applied only to the keys in ``layout``, so buttons this
        editor does not know about keep whatever the admin set elsewhere.
        """
        hidden = hidden or set()
        try:
            async with Session() as session:
                result = await session.execute(select(KeyboardButton))
                rows = {row.button_key: row for row in result.scalars().all()}
                for key, row in rows.items():
                    placement = layout.get(key)
                    row.sort_row = placement[0] if placement else None
                    row.sort_order = placement[1] if placement else None
                    if key in layout:
                        row.hidden = key in hidden
                for key, (row_index, order) in layout.items():
                    if key in rows:
                        continue
                    session.add(
                        KeyboardButton(
                            button_key=key,
                            button_text="",
                            sort_row=row_index,
                            sort_order=order,
                            hidden=key in hidden,
                        )
                    )
                await session.commit()
                invalidate_keyboard_button_cache()
                return True
        except SQLAlchemyError:
            return False

    async def reset_home_layout(self) -> bool:
        """Drop the stored layout and unhide every button."""
        try:
            async with Session() as session:
                result = await session.execute(select(KeyboardButton))
                for row in result.scalars().all():
                    row.sort_row = None
                    row.sort_order = None
                    row.hidden = False
                await session.commit()
                invalidate_keyboard_button_cache()
                return True
        except SQLAlchemyError:
            return False

    async def get_buttons_by_key_prefix(self, prefix: str) -> list[KeyboardButton]:
        cache = await _ensure_keyboard_button_cache()
        return [button for key, button in cache.items() if key.startswith(prefix)]

    async def delete_button(self, button_key: str) -> bool:

        try:
            async with Session() as session:
                stmt = select(KeyboardButton).where(KeyboardButton.button_key == button_key)
                result = await session.execute(stmt)
                button = result.scalars().first()
                if button:
                    await session.delete(button)
                    await session.commit()
                    invalidate_keyboard_button_cache()
                    return True
                return False
        except SQLAlchemyError:
            return False

    async def initialize_default_buttons(self):

        default_buttons = [
            # Inline MyService
            ("in.ms.change_sub", "🔗 تغییر ساب", "دکمه تغییر ساب"),
            ("in.ms.change_link", "🔗 تغییر لینک", "دکمه تغییر لینک"),
            ("in.ms.copy_link", "🔗 کپی لینک", "دکمه کپی لینک"),
            ("in.ms.info", "⚙️ نمایش اطلاعات بیشتر", "دکمه نمایش اطلاعات بیشتر"),
            ("in.ms.extra_volume", "♾️ حجم اضافه", "دکمه خرید حجم اضافه"),
            ("in.ms.extend_time", "📅 تمدید زمان", "دکمه تمدید زمان"),
            ("in.ms.extend_service", "💎 تمدیدسرویس", "دکمه تمدید سرویس"),
            ("in.ms.qrcode", "🔘 دریافت Qrcode", "دکمه دریافت QR Code"),
            ("in.ms.transfer_config", "🔎 واگذاری کانفیگ", "دکمه واگذاری کانفیگ"),
            ("in.ms.other_links", "➕ نمایش لینک‌های دیگر", "دکمه نمایش لینک‌های دیگر"),
            ("in.ms.show_clients", "🖥 نمایش کلاینت‌ها", "دکمه نمایش کلاینت‌ها"),
            ("in.ms.usage_chart", "📊 نمودار مصرف", "دکمه نمودار مصرف روزانه"),
            ("in.ms.delete_service", "🗑 حذف این کانفیگ برای همیشه", "دکمه حذف کانفیگ"),
            ("in.ms.back_to_services", "بازگشت به لیست سرویس‌ها", "دکمه بازگشت به لیست سرویس‌ها"),
            (
                "in.ms.renew.discount",
                "🎁 کد تخفیف (تمدید)",
                "دکمه کد تخفیف در صفحه تأیید تمدید اکانت (سرویس‌های من)",
            ),
            (
                "in.ms.renew.back",
                "◀️ بازگشت",
                "دکمه بازگشت در صفحه تأیید تمدید اکانت",
            ),
            (
                "in.ms.renew.confirm",
                "💎 تأیید تمدید اکانت",
                "دکمه تأیید نهایی تمدید اکانت",
            ),
            ("in.ms.sub_links.prev", "صفحه قبلی →", "صفحه قبل در لیست لینک‌های ساب"),
            ("in.ms.sub_links.next", "← صفحه بعدی", "صفحه بعد در لیست لینک‌های ساب"),
            (
                "in.ms.sub_links.get_all",
                "📥 دریافت تمام لینک‌های کانفیگ",
                "دریافت یکجا همه لینک‌ها",
            ),
            (
                "in.ms.sub_links.back",
                "بازگشت به قبل",
                "بازگشت از othersSubLinks به جزئیات سرویس",
            ),
            # Home Keyboards
            ("bt.menu_my_services", "🔑 سرویس های من", "دکمه 🔑 سرویس های من"),
            ("bt.menu_get_trial", "🎁 دریافت تست", "دکمه 🎁 دریافت تست"),
            ("bt.menu_buy_service", "🛍 خرید سرویس", "دکمه 🛍 خرید سرویس"),
            ("bt.menu_buy_reseller", "🏢 خرید پنل نمایندگی", "دکمه خرید پنل نمایندگی"),
            ("bt.menu_my_resellers", "📋 نمایندگی‌های من", "دکمه لیست نمایندگی‌های کاربر"),
            ("bt.menu_profile", "🙍 پروفایل من", "دکمه 🙍 پروفایل من"),
            ("bt.menu_add_balance", "💰 افزایش موجودی", "دکمه 💰 افزایش موجودی"),
            ("bt.menu_support", "☎️ پشتیبانی", "دکمه ☎️ پشتیبانی"),
            ("bt.menu_uptime", "🔋 وضعیت سرویس ها", "دکمه 🔋 وضعیت سرویس ها"),
            ("bt.menu_help", "📚 راهنما", "دکمه 📚 راهنما"),
            ("bt.menu_advanced_settings", "⚙️ تنظیمات پیشرفته", "دکمه ⚙️ تنظیمات پیشرفته"),
            ("bt.menu_admin_panel", "⚙️ پنل مدیریت", "دکمه ⚙️ پنل مدیریت"),
            # Balance / charge inline buttons
            ("in.balance.stars", "⭐ پرداخت با استارز", "دکمه پرداخت با استارز"),
            ("in.balance.crypto", "💵 پرداخت ارزی", "دکمه ورود به پرداخت ارزی"),
            ("in.balance.manual", "💳 کارت به کارت (تایید زیر 5 دقیقه)", "دکمه کارت به کارت دستی"),
            ("in.balance.auto", "💷 کارت به کارت خودکار", "دکمه کارت به کارت خودکار"),
            ("in.balance.disabled", "❌ شارژ حساب غیرفعال می‌باشد", "دکمه زمانی که هیچ روش پرداختی فعال نیست"),
            ("in.balance.referral", "🎁 دعوت دوستان", "دکمه دعوت دوستان در منوی شارژ"),
            ("in.balance.trx", "💵 پرداخت با TRX (ترون)", "دکمه پرداخت TRX"),
            ("in.balance.usdt", "💵 پرداخت با USDT (تتر)", "دکمه پرداخت USDT"),
            ("in.balance.ton", "💎 پرداخت با TON (تون)", "دکمه پرداخت TON"),
            ("in.balance.crypto_back", "🔙 بازگشت به روش‌های پرداخت", "دکمه بازگشت از منوی ارز به شارژ"),
            ("in.balance.send_receipt", "💰 پرداخت کردم | ارسال رسید واریزی", "دکمه ارسال رسید کارت دستی"),
            (
                "in.balance.flow_cancel",
                "🔙 انصراف · بازگشت به منوی شارژ",
                "دکمه انصراف در مراحل شارژ (کارت، ارز، استارز)",
            ),
            (
                "in.balance.back_home",
                "🏠 بازگشت به منوی اصلی",
                "دکمه بازگشت به منوی اصلی از منوی شارژ",
            ),
            # Buy service inline buttons
            ("in.buy.cancel", "❌ انصراف", "دکمه انصراف در فلو خرید سرویس"),
            ("in.buy.back", "🔙 بازگشت", "دکمه بازگشت در فلو خرید سرویس"),
            ("in.buy.confirm", "✅ تأیید خرید", "دکمه تأیید خرید سرویس/اکانت"),
            ("in.buy.discount", "🎉 اعمال کد تخفیف", "دکمه اعمال کد تخفیف هنگام خرید"),
            ("in.buy.default_username", "🎲 اسم پیشفرض ربات", "دکمه نام کاربری تصادفی هنگام خرید VPN"),
            (
                "in.buy.retry_username",
                "🔄 تغییر مجدد نام کانفیگ",
                "دکمه انتخاب مجدد نام کانفیگ پس از تکراری بودن در پنل",
            ),
            (
                "in.buy.custom",
                "🧩 حجم و زمان دلخواه",
                "دکمه خرید حجم و زمان دلخواه در فلو خرید سرویس",
            ),
            ("in.buy.empty_list", "🚀 خرید اکانت ویتوری", "دکمه خرید وقتی کاربر سرویسی ندارد"),
        ]

        try:
            async with Session() as session:
                result = await session.execute(select(KeyboardButton))
                rows = list(result.scalars().all())
                existing_keys = {row.button_key for row in rows}
                missing = [
                    KeyboardButton(button_key=key, button_text=text, description=desc)
                    for key, text, desc in default_buttons
                    if key not in existing_keys
                ]
                if missing:
                    session.add_all(missing)
                # An older build wrote the decoration brackets into the stored
                # label. The glassy look is a keyboard flag now, so the brackets
                # are dropped here once: handlers match a press against this same
                # stored text, so leaving them would show them on every button.
                changed = False
                for row in rows:
                    plain = unglass_text(row.button_text)
                    if row.button_text and plain != row.button_text:
                        row.button_text = plain
                        changed = True
                if missing or changed:
                    await session.commit()
        except SQLAlchemyError:
            pass
        invalidate_keyboard_button_cache()


async def get_button_text(button_key: str, default: str | None = None) -> str:

    keyboard_crud = KeyboardButtonCRUD()
    text = await keyboard_crud.get_button_text(button_key)
    if text:
        return unglass_text(text)

    return default if default is not None else button_key
