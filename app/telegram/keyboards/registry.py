"""Keyboard customization registry: titles, defaults, and style labels."""

from app.i18n import DEFAULT_LANGUAGE, namespace, t
from app.services.payments.ir_gateways.providers import GATEWAYS

KEYBOARD_BUTTON_TITLES = {
    "bt.menu_my_services": "سرویس های من",
    "bt.menu_get_trial": "دریافت تست",
    "bt.menu_buy_service": "خرید سرویس",
    "bt.menu_buy_reseller": "خرید پنل نمایندگی",
    "bt.menu_my_resellers": "نمایندگی‌های من",
    "bt.menu_profile": "پروفایل من",
    "bt.menu_add_balance": "افزایش موجودی",
    "bt.menu_support": "پشتیبانی",
    "bt.menu_uptime": "وضعیت سرویس ها",
    "bt.menu_help": "راهنما",
    "bt.menu_advanced_settings": "تنظیمات پیشرفته",
    "bt.menu_admin_panel": "پنل مدیریت",
    "bt.menu_miniapp": "ورود به اپلیکیشن",
    "bt.menu_miniapp_open": "دکمه شیشه‌ای باز کردن اپلیکیشن",
    "in.ms.change_sub": "تغییر ساب",
    "in.ms.change_link": "تغییر لینک",
    "in.ms.copy_link": "کپی لینک",
    "in.ms.info": "نمایش اطلاعات بیشتر",
    "in.ms.extra_volume": "حجم اضافه",
    "in.ms.extend_time": "تمدید زمان",
    "in.ms.extend_service": "تمدید سرویس",
    "in.ms.qrcode": "دریافت Qrcode",
    "in.ms.transfer_config": "واگذاری کانفیگ",
    "in.ms.other_links": "نمایش لینک‌های دیگر",
    "in.ms.show_clients": "نمایش کلاینت‌ها",
    "in.ms.usage_chart": "نمودار مصرف",
    "in.ms.delete_service": "حذف کانفیگ",
    "in.ms.back_to_services": "بازگشت به لیست سرویس‌ها",
    "in.ms.renew.discount": "کد تخفیف (تمدید اکانت)",
    "in.ms.renew.back": "بازگشت (تمدید اکانت)",
    "in.ms.renew.confirm": "تأیید تمدید اکانت",
    "in.ms.sub_links.prev": "صفحه قبلی (لینک‌ها)",
    "in.ms.sub_links.next": "صفحه بعدی (لینک‌ها)",
    "in.ms.sub_links.get_all": "دریافت همه لینک‌ها",
    "in.ms.sub_links.back": "بازگشت (لینک‌های دیگر)",
    "in.balance.crypto": "پرداخت ارزی",
    "in.balance.stars": "پرداخت با استارز",
    "in.balance.tonpays": "پرداخت با TonPays",
    "in.balance.manual": "کارت به کارت (دستی)",
    "in.balance.auto": "کارت به کارت خودکار",
    "in.balance.disabled": "شارژ غیرفعال",
    "in.balance.referral": "دعوت دوستان",
    "in.balance.trx": "پرداخت TRX",
    "in.balance.usdt": "پرداخت USDT",
    "in.balance.usdt_ton": "پرداخت USDT-TON",
    "in.balance.usdt_bep20": "پرداخت USDT-BEP20",
    "in.balance.ton": "پرداخت TON",
    "in.balance.pol": "پرداخت POL",
    "in.balance.crypto_back": "بازگشت به روش‌های پرداخت",
    "in.balance.send_receipt": "ارسال رسید واریزی",
    "in.balance.flow_cancel": "انصراف (منوی شارژ)",
    "in.balance.back_home": "بازگشت به منوی اصلی",
    "in.buy.cancel": "انصراف (خرید)",
    "in.buy.back": "بازگشت (خرید)",
    "in.buy.confirm": "تأیید خرید",
    "in.buy.topup": "افزایش موجودی (فاکتور با موجودی ناکافی)",
    "in.buy.discount": "اعمال کد تخفیف",
    "in.buy.default_username": "اسم پیشفرض ربات",
    "in.buy.retry_username": "تغییر مجدد نام کانفیگ",
    "in.buy.custom": "خرید حجم و زمان دلخواه",
    "in.buy.empty_list": "خرید (بدون سرویس)",
    "in.rs.show_creds": "نمایش رمز ورود",
    "in.rs.change_password": "تغییر رمز عبور",
    "in.rs.resume": "فعال‌سازی پنل",
    "in.rs.pause": "غیرفعال‌سازی پنل",
    "in.rs.renew": "تمدید نمایندگی",
    "in.rs.usage_report": "گزارش مصرف",
    "in.rs.usage_cap": "محدودیت مصرف",
    "in.rs.usage_cap_set": "تنظیم سقف (گیگ)",
    "in.rs.usage_cap_clear": "حذف سقف مصرف",
    "in.rs.buy_user_capacity": "یوزر اضافه (نمایندگی)",
    "in.rs.extra_days": "روز اضافه (نمایندگی)",
    "in.rs.extra_volume": "حجم اضافه (نمایندگی)",
    "in.rs.delete": "حذف نمایندگی",
    "in.rs.buy_random_username": "نام تصادفی (نمایندگی)",
    "in.rs.delete_confirm": "تأیید حذف نمایندگی",
    "in.rs.delete_final": "تأیید نهایی حذف نمایندگی",
    "in.rs.chpwd_confirm": "تأیید تغییر رمز",
}


KEYBOARD_BUTTON_DEFAULTS: dict[str, str] = namespace("buttons", DEFAULT_LANGUAGE)

# One balance button per Iranian direct gateway, generated so a new provider needs no edit here.
for _provider in GATEWAYS.values():
    KEYBOARD_BUTTON_TITLES[f"in.balance.{_provider.key}"] = f"پرداخت با {_provider.title}"
    KEYBOARD_BUTTON_DEFAULTS[f"in.balance.{_provider.key}"] = t(
        "button_templates.gateway_payment", DEFAULT_LANGUAGE, emoji=_provider.emoji, title=_provider.title
    )


KEYBOARD_BUTTON_DEFAULT_STYLES = {
    "in.buy.topup": ("success", None),
    "bt.menu_miniapp": ("primary", None),
    "bt.menu_miniapp_open": ("primary", None),
    "bt.menu_my_services": ("primary", 5895443668663275064),
    "bt.menu_buy_service": ("success", 5373052667671093676),
    "in.buy.custom": ("primary", None),
    "in.rs.delete_final": ("danger", None),
}

STYLE_LABELS = {
    "primary": "آبی",
    "success": "سبز",
    "danger": "قرمز",
}
