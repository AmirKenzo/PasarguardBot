"""Shared anti-spam state and logic (no app.telegram imports — avoids circular imports)."""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass
from typing import Literal

from config import ADMIN_ID

ANTI_SPAM_TEXT = [
    "⛔ رباتم داره دود می‌کنه! {seconds_block} ثانیه استراحت بده! 🔥",
    "🤖 آروم‌تر سرباز! {seconds_block} ثانیه دیگه بیا جنگ کنیم. 🪖",
    "🛑 اسپم خطرناکه! {seconds_block} ثانیه توقیف شدی. 🚓",
    "😂 آرام جان، اینجا رباته نه فرمول یک! {seconds_block} ثانیه وایسا.",
    "💤 ربات به خواب رفت! {seconds_block} ثانیه بعد بیدار میشه.",
    "🚀 با این سرعت رفتی مریخ! حالا {seconds_block} ثانیه صبر کن.",
    "⚡ سرعتت رو کنترل کن! {seconds_block} ثانیه خاموشی.",
    "☕ یه قهوه بخور و برگرد! {seconds_block} ثانیه فاصله لازمه.",
    "📵 ارتباط قطع شد. {seconds_block} ثانیه بعد دوباره تلاش کن.",
    "🧘‍♂️ آرامش کلید موفقیته! {seconds_block} ثانیه استراحت.",
    "🛑 فشار زیاد باعث انفجار میشه! {seconds_block} ثانیه توقف کن. 💥",
    "🔒 موقتاً قفل شدی، {seconds_block} ثانیه صبر کن.",
    "🧹 درحال پاکسازی اسپم... لطفاً {seconds_block} ثانیه منتظر بمون.",
    "🤹‍♂️ رباتم داره تردستی درمیاره! {seconds_block} ثانیه وقت بده.",
    "🚨 هشدار اسپم: {seconds_block} ثانیه ممنوع الورود شدی!",
    "😅 اوه، زیادی هیجان زده شدی! {seconds_block} ثانیه نفس بگیر.",
    "🎮 ربات تو حالت pause رفت! {seconds_block} ثانیه دیگه play بده.",
    "🚦 چراغ قرمز شدی! {seconds_block} ثانیه توقف اجباری.",
    "🧠 مغز ربات هنگ کرد! لطفاً {seconds_block} ثانیه صبر کن.",
    "🎭 یه نفس بگیر، {seconds_block} ثانیه تئاتر تعطیله!",
    "🔥 سیستم خنک‌کننده فعال شد... {seconds_block} ثانیه یخ بزن! ❄️",
    "🤖 انرژی ربات تموم شد! {seconds_block} ثانیه شارژ لازمه.",
    "🚧 تعمیرات اضطراری! {seconds_block} ثانیه ممنوع الورود.",
    "📈 با این سرعت رکورد جهانی میزنی! ولی فعلاً {seconds_block} ثانیه استراحت.",
    "🎯 صبر کن تا هدف رو درست بزنی! {seconds_block} ثانیه فاصله بگیر.",
    "🎲 اسپم ممنوع! بازی تازه {seconds_block} ثانیه دیگه شروع میشه.",
    "🛡️ سیستم ضداسپم فعال شد! {seconds_block} ثانیه توقف.",
    "👀 کسی داره اسپم میکنه... اوه تو بودی! {seconds_block} ثانیه استراحت.",
    "🧩 یه تیکه پازل گم شده، {seconds_block} ثانیه زمان بده پیدا کنیم.",
    "🪫 باتری ربات خالی شد! {seconds_block} ثانیه شارژ لازم داری.",
    "🏖️ وقتشه یه {seconds_block} ثانیه بری تعطیلات کوتاه!",
    "🧳 ربات رفته سفر! {seconds_block} ثانیه بعد برمیگرده.",
    "🍿 پاپ‌کورن بگیر و فیلم ببین، {seconds_block} ثانیه وقت داریم. 😄",
    "🦾 ربات نیاز به سرویس فنی داره، {seconds_block} ثانیه در صف بمون.",
    "🛬 اسپم زیاد باعث فرود اضطراری شد! {seconds_block} ثانیه صبر کن.",
    "🏃‍♂️ ندو! با حوصله بیا، {seconds_block} ثانیه دیگه.",
    "🧨 اسپم‌ت باعث انفجار شد! لطفاً {seconds_block} ثانیه به دور بمون.",
    "👻 سرعتت ماورایی بود! {seconds_block} ثانیه تو دنیای ارواح سر کن!",
    "🏆 اسپمر نمونه شدی ولی فعلاً {seconds_block} ثانیه جایزه نداری. 😂",
    "🧿 چشم ربات زدیا! {seconds_block} ثانیه چشم نظر بگیر.",
    "🧬 با این سرعت داری DNA بازنویسی می‌کنی! {seconds_block} ثانیه فاصله بگیر.",
    "🦄 افسانه‌ها میگن کسی اینقدر سریع اسپم نکرده بود! {seconds_block} ثانیه افسانه باش.",
    "🎃 ربات ترسید! {seconds_block} ثانیه ریکاوری لازم داره.",
    "🚢 کشتی رباتت غرق شد! {seconds_block} ثانیه منتظر کشتی نجات باش.",
    "🛡️ در حالت دفاع از ربات هستیم! {seconds_block} ثانیه بیرون بمون.",
    "🧹 در حال تمیز کردن اسپم‌ها... لطفاً {seconds_block} ثانیه کمک نکن. 😂",
    "🪄 جادوی اسپم رو از دست دادی! {seconds_block} ثانیه بعد بیا.",
    "🛰️ سیگنال قطع شد، {seconds_block} ثانیه منتظر اتصال باش.",
    "🛤️ مسیرت به بن‌بست خورد! {seconds_block} ثانیه دنده عقب بگیر.",
    "🎢 مثل ترن هوایی رفتی بالا، ولی فعلاً {seconds_block} ثانیه توقف.",
]

SPAM_BLOCK_SECONDS = 10
MIN_MESSAGE_INTERVAL = 0.8

user_last_message_time: dict[int, float] = {}
user_last_event_id: dict[int, int] = {}
user_blocked_until: dict[int, float] = {}
user_spam_events: dict[str, float] = {}
antispam_lock = asyncio.Lock()


@dataclass(frozen=True)
class AntispamResult:
    action: Literal["allow", "allow_same_event", "block", "spam"]
    notify_message: str | None = None


def _spam_event_key(user_id: int, event_id: int | None) -> str | None:
    if event_id is None:
        return None
    return f"{user_id}_{event_id}"


def _cleanup_spam_events(now: float) -> None:
    keys_to_delete = [k for k, v in user_spam_events.items() if now - v > 60]
    for k in keys_to_delete:
        user_spam_events.pop(k, None)


def check_antispam(
    user_id: int,
    event_id: int | None,
    *,
    now: float | None = None,
    block_seconds: int = SPAM_BLOCK_SECONDS,
    min_interval: float = MIN_MESSAGE_INTERVAL,
) -> AntispamResult:
    """
    Synchronous antispam decision (call inside antispam_lock).
    Does not send Telegram messages.
    """
    if user_id in ADMIN_ID:
        return AntispamResult(action="allow")

    now = now if now is not None else time.time()

    if event_id is not None:
        spam_key = _spam_event_key(user_id, event_id)
        if spam_key and spam_key in user_spam_events:
            return AntispamResult(action="block")

    if user_blocked_until.get(user_id, 0) > now:
        return AntispamResult(action="block")

    if event_id is not None and user_last_event_id.get(user_id) == event_id:
        return AntispamResult(action="allow_same_event")

    last_time = user_last_message_time.get(user_id, 0)
    if last_time > 0 and (now - last_time) < min_interval:
        user_blocked_until[user_id] = now + block_seconds
        if event_id is not None:
            spam_key = _spam_event_key(user_id, event_id)
            if spam_key:
                user_spam_events[spam_key] = now
                _cleanup_spam_events(now)
        msg = random.choice(ANTI_SPAM_TEXT).format(seconds_block=block_seconds)
        return AntispamResult(action="spam", notify_message=msg)

    user_last_message_time[user_id] = now
    if event_id is not None:
        user_last_event_id[user_id] = event_id

    return AntispamResult(action="allow")
