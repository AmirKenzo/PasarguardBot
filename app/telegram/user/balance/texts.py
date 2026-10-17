"""Text templates for user balance."""

from app.utils.text.default_texts import DEFAULT_BOT_TEXTS

MANUAL_CARD_INFO_DEFAULT = DEFAULT_BOT_TEXTS["manual_card_info"]

ADD_BALANCE_INTRO_DEFAULT = DEFAULT_BOT_TEXTS["add_balance_intro"]

MANUAL_CARD_AMOUNT_REQUEST_DEFAULT = DEFAULT_BOT_TEXTS["manual_card_amount_request"]

MANUAL_CARD_RECEIPT_REQUEST_DEFAULT = DEFAULT_BOT_TEXTS["manual_card_receipt_request"]

MANUAL_CARD_RECEIPT_CONFIRMED_DEFAULT = DEFAULT_BOT_TEXTS["manual_card_receipt_confirmed"]

MANUAL_CARD_LOG_CHANNEL_MISSING_DEFAULT = DEFAULT_BOT_TEXTS["manual_card_log_channel_missing"]

MANUAL_CARD_RECEIPT_PHOTO_ERROR_DEFAULT = DEFAULT_BOT_TEXTS["manual_card_receipt_photo_error"]

MANUAL_CARD_AMOUNT_RANGE_ERROR_DEFAULT = DEFAULT_BOT_TEXTS["manual_card_amount_range_error"]

MANUAL_CARD_NUMERIC_ERROR_DEFAULT = DEFAULT_BOT_TEXTS["manual_card_numeric_error"]

AUTO_CARD_AMOUNT_RANGE_ERROR_DEFAULT = (
    "⚠️ خطا ⚠️\n\n"
    "❌ مبلغ باید بین {min_amount} تا {max_amount} تومان باشد.\n\n"
    "🌀 مثلا برای شارژ ۵۰ هزار تومان بنویسید: 50000"
)

AUTO_CARD_NUMERIC_ERROR_DEFAULT = "⚠️ لطفا فقط عدد ارسال کنید."

CRYPTO_AMOUNT_RANGE_ERROR_DEFAULT = DEFAULT_BOT_TEXTS["crypto_amount_range_error"]

CRYPTO_NUMERIC_ERROR_DEFAULT = DEFAULT_BOT_TEXTS["crypto_numeric_error"]

STARS_AMOUNT_RANGE_ERROR_DEFAULT = (
    "⚠️ خطا ⚠️\n\n"
    "❌ مبلغ باید بین {min_amount} تا {max_amount} تومان باشد.\n\n"
    "🌀 مثلا برای شارژ ۱۰۰ هزار تومان بنویسید: 100000"
)

STARS_NUMERIC_ERROR_DEFAULT = "⚠️ لطفا فقط عدد ارسال کنید."

PAYMENT_DISABLED_ALERT = "این روش پرداخت موقتا غیرفعال میباشد"
AUTO_CARD_SAFE_DISABLED_ALERT = (
    "این قابلیت برای شما فعال نیست\nبرای فعال شدن شما باید حداقل 5 کارت به کارت معمولی داشته باشید"
)
NO_CRYPTO_WALLET_ALERT = "❌ هیچ کیف پول ارزی ثبت نشده است."
CRYPTO_SELECT_PROMPT = "💵 **پرداخت ارزی**\n\nلطفاً نوع ارز مورد نظر خود را انتخاب کنید:"
CRYPTO_TRX_CURRENCY = "💵 **ارز:** TRX (ترون)"
CRYPTO_USDT_CURRENCY = "💵 **ارز:** USDT (تتر - شبکه ترون)"
CRYPTO_USDT_TON_CURRENCY = "💵 **ارز:** USDT (تتر - شبکه تون)"
CRYPTO_USDT_BEP20_CURRENCY = "💵 **ارز:** USDT (تتر - شبکه بایننس)"
CRYPTO_TON_CURRENCY = "💎 **ارز:** TON (تون)"
CRYPTO_POL_CURRENCY = "🔷 **ارز:** POL (پالیگان)"
CRYPTO_AMOUNT_PROMPT_TEMPLATE = (
    "💰 مبلغ شارژ را به **تومان** (فقط عدد) ارسال کنید.\n\n"
    "📉 حداقل: `{min}` | 📈 حداکثر: `{max}`\n"
    "{currency}\n\n"
    "پس از ثبت، آدرس کیف پول و مبلغ دقیق واریز نمایش داده می‌شود."
)
STARS_AMOUNT_PROMPT_TEMPLATE = (
    "⭐ **پرداخت با استارز تلگرام**\n\n"
    "💰 مبلغ شارژ را به **تومان** (فقط عدد) ارسال کنید.\n\n"
    "📉 حداقل: `{min}` | 📈 حداکثر: `{max}`\n\n"
    "پس از ثبت مبلغ، فاکتور استارز برای شما ارسال می‌شود."
)
AUTO_CARD_AMOUNT_PROMPT_TEMPLATE = (
    "💰 مبلغ شارژ را به **تومان** (فقط عدد) ارسال کنید.\n\n"
    "📉 حداقل: `{min}` | 📈 حداکثر: `{max}`\n\n"
    "✅ پرداخت خودکار است؛ مبلغ ریالی نمایش‌داده‌شده را دقیق واریز کنید."
)
ENTER_AMOUNT_FIRST_ALERT = "ابتدا مبلغ شارژ را وارد کنید."
FLOW_NOT_CANCELLABLE_ALERT = "این مرحله قابل لغو نیست."
RETURN_HOME_TEXT = "🏠 به منوی اصلی بازگشتید."
NO_CARD_REGISTERED = "شماره کارت ثبت نشده"
CRYPTO_INVOICE_CREATE_FAILED = "❌ ساخت فاکتور انجام نشد. لطفاً دوباره تلاش کنید."
PENDING_ORDERS_LIMIT = "⚠️ شما بیش از سه فاکتور در انتظار دارید. لطفاً ابتدا فاکتورهای قبلی را پرداخت کنید."
WALLET_NOT_FOUND_TRX = "❌ کیف پول ترون در سیستم ثبت نشده است. لطفاً با پشتیبانی تماس بگیرید."
WALLET_NOT_FOUND_USDT = "❌ کیف پول USDT در سیستم ثبت نشده است. لطفاً با پشتیبانی تماس بگیرید."
WALLET_NOT_FOUND_USDT_TON = "❌ کیف پول USDT-TON در سیستم ثبت نشده است. لطفاً با پشتیبانی تماس بگیرید."
WALLET_NOT_FOUND_USDT_BEP20 = "❌ کیف پول USDT-BEP20 در سیستم ثبت نشده است. لطفاً با پشتیبانی تماس بگیرید."
WALLET_NOT_FOUND_TON = "❌ کیف پول TON در سیستم ثبت نشده است. لطفاً با پشتیبانی تماس بگیرید."
WALLET_NOT_FOUND_POL = "❌ کیف پول POL در سیستم ثبت نشده است. لطفاً با پشتیبانی تماس بگیرید."

OPEN_TONKEEPER_LABEL = "پرداخت با TON Keeper"

REFERRAL_BANNER = (
    " بنر شما برای دعوت دیگران به ربات\n"
    "🎁 با دعوت دوستان به ربات با لینک اختصاصی خود میتوانید به ازای هر نفر 500 تومان موجودی دریافت کنید\n"
    "❕ بعد از عضویت هر نفر در کانال ما، موجودی بصورت خودکار افزوده میشود .\n"
)

PHONE_VERIFY_PROMPT = (
    "🔐 به منظور افزایش امنیت پرداخت‌ها و ارائه اطلاع‌رسانی‌های دقیق از طریق ربات،"
    "\n\n"
    "👈 لطفاً شماره تماس مرتبط با اکانت خود را از طریق دکمه زیر به اشتراک بگذارید. \n\n"
    "✅ توجه: شماره شما کاملاً محرمانه بوده و صرفاً برای اطمینان از صحت اطلاعات و ارائه خدمات بهتر استفاده خواهد شد."
)
PHONE_VERIFY_WRONG_USER = "🚫 فقط می‌توانید شماره تلفن متعلق به خودتان را ارسال کنید.\n❌ ارسال شماره‌های دیگر مجاز نیست."
PHONE_VERIFY_SUCCESS = (
    "✅ شماره تلفن شما با موفقیت ثبت شد.\n"
    "🌟 از اعتماد شما به مجموعه ما سپاسگزاریم! ما متعهد به حفظ حریم خصوصی و ارائه بهترین خدمات به شما هستیم.\n"
    "📌 در صورت نیاز به پشتیبانی، همواره می‌توانید با ما در تماس باشید. 🙏\n"
)
PHONE_VERIFY_UPDATE_ERROR = (
    "⛔ متأسفیم! خطایی در به‌روزرسانی شماره تلفن شما رخ داد.\n"
    "لطفاً دوباره تلاش کنید یا در صورت ادامه مشکل، با پشتیبانی تماس بگیرید. 🙏"
)
PHONE_VERIFY_INVALID_PREFIX = (
    "🚫 فقط شماره‌هایی که با پیش‌شماره +98 شروع می‌شوند قابل پذیرش هستند.\n👈 لطفاً یک شماره معتبر ایرانی وارد کنید."
)
DEFAULT_USERNAME = "یوزرنیم موجود نیست"

COPY_AMOUNT_LABEL = "برای کپی کردن مبلغ کلیک کنید"
COPY_WALLET_LABEL = "برای کپی کردن ادرس ولت کلیک کنید"

AUTO_CARD_INVOICE_TEMPLATE = (
    "✅ فاکتور کارت به کارت شما صادر شد\n\n"
    "➿ شماره فاکتور : {order}\n"
    "🕰 مهلت پرداخت : 30 دقیقه\n\n"
    "💵 مبلغ : <code>{rials:,}</code> ریال\n\n"
    "👈 مبلغ بالا را بصورت دقیق به کارت زیر واریز کنید \n\n"
    "💳 <code>{card_num}</code>\n"
    "👤 بنام :  {card_name}\n\n"
    "⚠️ توجه کنید :  مبلغ به ریالی که ربات نمایش داده رو کپی کنید درغیراینصورت تراکنش شما به صورت خودکار تایید نمیشود ( به سه رقم آخر مبلغ ریالی، دقت فرمایید )"
)

DUPLICATE_RECEIPT_LOG_HEADER = "🚫 #کارت_به_کارت_تکراری\n"
MANUAL_RECEIPT_LOG_HEADER = "💳 #کارت_به_کارت\n"
# Admin receipt log line when the receipt image could not be hashed (no duplicate check, no auto-approve).
DUPLICATE_CHECK_UNAVAILABLE_LOG_LINE = "⚠️ **بررسی رسید تکراری انجام نشد** (پردازش تصویر ناموفق بود؛ فقط تایید دستی)"
