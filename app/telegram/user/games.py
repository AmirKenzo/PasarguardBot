"""User games: the /games menu, rock-paper-scissors and the /dice shortcut, one play per day."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from telethon import Button, events
from telethon.tl.functions.messages import SendMediaRequest
from telethon.tl.types import InputMediaDice

from app.db.crud.user import UserCRUD, update_Money
from app.logger import LogType, get_logger
from app.telegram.plugins import PluginContext
from app.telegram.shared.utils.logging import send_log_message
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.shared.utils.rate_limit import debounce_callback

MODULE_NAME = "user.games"
MODULE_VERSION = "1.1.0"
MODULE_DESCRIPTION = "User games and rewards"

logger = get_logger(__name__)

REWARDS = [500, 600, 700, 800, 900, 1000, 2000, 3000, 4000, 5000, 6000, 10000]
DICE_SHORTCUT_REWARDS = [1000, 1500, 2000, 3000]
RPS_TIE_PRIZE = 200
RPS_EMOJIS = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
RPS_NAMES = {"rock": "سنگ", "paper": "کاغذ", "scissors": "قیچی"}
RPS_BEATS = {"rock": "scissors", "paper": "rock", "scissors": "paper"}

LOSE_TAIL = " متأسفانه برنده نشدید. 😥 شانس خود را فردا دوباره امتحان کنید! 🍀"
GAMES_MENU = (
    "🎮 **منوی بازی‌های جذاب** 🎮\n\n"
    "🎲 تاس - شانس برنده شدن با عدد 6\n"
    "🎯 دارت - امتیاز بالا برای برنده شدن\n"
    "🏀 بسکتبال - شوت موفق برای برنده شدن\n"
    "⚽ فوتبال - گل زدن برای برنده شدن\n"
    "🎳 بولینگ - استرایک برای برنده شدن\n"
    "✂️ سنگ کاغذ قیچی - رقابت با ربات\n"
    "💡 هر بازی روزی یکبار قابل انجام است!"
)
RPS_HEADER = "✂️ **بازی سنگ کاغذ قیچی** ✂️\n\n"


@dataclass(frozen=True)
class DiceGame:
    emoji: str
    min_win: int
    win_how: str
    log_how: str
    lose: str


DICE_GAMES: dict[str, DiceGame] = {
    "dice": DiceGame("🎲", 6, "با آوردن عدد 6", "با انداختن تاس، عدد 6 آورد", "🎲 تاس شما روی عدد {value} ایستاد!"),
    "darts": DiceGame(
        "🎯", 6, "با امتیاز {value}", "با دارت، امتیاز {value} آورد", "🎯 دارت شما روی امتیاز {value} ایستاد!"
    ),
    "basketball": DiceGame("🏀", 4, "با شوت موفق", "با بسکتبال، شوت موفق زد", "🏀 شوت شما موفق نبود!"),
    "football": DiceGame("⚽", 6, "با گل زدن", "با فوتبال، گل زد", "⚽ گل شما موفق نبود!"),
    "slot": DiceGame("🎰", 6, "با ترکیب موفق", "با ماشین اسلات، ترکیب موفق کرد", "🎰 ترکیب شما موفق نبود!"),
    "bowling": DiceGame("🎳", 6, "با استرایک", "با بولینگ، استرایک کرد", "🎳 استرایک شما موفق نبود!"),
}


def _win_text(how: str, prize: int) -> str:
    return f"🎉 تبریک می‌گم! شانس با شما یار بود و {how} مبلغ {prize:,} تومان به حساب شما اضافه شد! 💰"


def _balance_button(label: str, amount: int) -> list:
    return [Button.inline(f"💳 {label}: {amount:,} تومان", data="no_action")]


def _menu_buttons() -> list:
    return [
        [Button.inline("🎲 تاس", "game_dice"), Button.inline("🎯 دارت", "game_darts")],
        [Button.inline("🏀 بسکتبال", "game_basketball"), Button.inline("⚽ فوتبال", "game_football")],
        [Button.inline("✂️ سنگ کاغذ قیچی", "game_rps"), Button.inline("🎳 بولینگ", "game_bowling")],
    ]


def _rps_buttons() -> list:
    return [
        [Button.inline("🪨 سنگ", "rps_rock"), Button.inline("📄 کاغذ", "rps_paper")],
        [Button.inline("✂️ قیچی", "rps_scissors")],
    ]


def _remaining(last_play: float | None) -> str | None:
    """Time left until the next play, or None when the user can play now."""
    left = datetime.fromtimestamp(last_play or 0) + timedelta(days=1) - datetime.now()
    if left.total_seconds() <= 0:
        return None
    hours, rest = divmod(left.seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    parts = [(left.days, "روز"), (hours, "ساعت"), (minutes, "دقیقه"), (seconds, "ثانیه")]
    return ",".join(f"{amount} {unit}" for amount, unit in parts if amount > 0)


async def _roll(event, emoji: str) -> int:
    updates = await event.client(
        SendMediaRequest(peer=event.sender_id, media=InputMediaDice(emoticon=emoji), message="")
    )
    await UserCRUD().update_user(user_id=event.sender_id, last_dice_roll=datetime.now().timestamp())
    return updates.updates[1].message.media.value


@bot_is_offline
async def games_command(event) -> None:
    await event.reply(GAMES_MENU, buttons=_menu_buttons())
    raise events.StopPropagation


@bot_is_offline
@debounce_callback()
async def back_to_games(event) -> None:
    await event.edit(GAMES_MENU, buttons=_menu_buttons())


@bot_is_offline
async def dice_shortcut(event) -> None:
    user_id = event.sender_id
    user = await UserCRUD().read_user(user_id)
    remaining = _remaining(user.last_dice_roll if user else None)
    if remaining:
        await event.reply(
            f"<blockquote expandable>👻 شما بعد از {remaining} دیگر مجدد میتونید تاس بندازید</blockquote>",
            parse_mode="html",
        )
        raise events.StopPropagation

    value = await _roll(event, "🎲")
    if value == 6:
        prize = random.choice(DICE_SHORTCUT_REWARDS)
        new_amount = await update_Money(user_id=user_id, Money=prize)
        await event.reply(_win_text("با آوردن عدد 6", prize), buttons=_balance_button("موجودی جدید شما", new_amount))
        await send_log_message(
            LogType.OTHER,
            message=f"🎲 کاربر خوش‌شانس {user_id} با انداختن تاس، عدد 6 آورد و برنده مبلغ {prize:,} تومان شد! 🎉",
            buttons=_balance_button("موجودی جدید کاربر", new_amount),
        )
    else:
        await event.reply(f"🎲 تاس شما روی عدد {value} ایستاد!{LOSE_TAIL}")
        await send_log_message(
            LogType.OTHER,
            message=f"🎲 کاربر {user_id} با انداختن تاس، عدد {value} را آورد. متأسفانه برنده نشد. 😥",
            buttons=_balance_button("موجودی فعلی کاربر", getattr(user, "amount", 0)),
        )
    raise events.StopPropagation


@bot_is_offline
@debounce_callback()
async def play_game(event) -> None:
    game_key = event.data.decode().split("_", 1)[1]
    user_id = event.sender_id
    user = await UserCRUD().read_user(user_id)
    remaining = _remaining(user.last_dice_roll if user else None)
    if remaining:
        await event.edit(
            f"<blockquote expandable>🎮 شما بعد از {remaining} دیگر مجدد میتونید بازی کنید</blockquote>",
            parse_mode="html",
        )
        return

    if game_key == "rps":
        await UserCRUD().update_user(user_id=user_id, last_dice_roll=datetime.now().timestamp())
        await event.edit(f"{RPS_HEADER}انتخاب کنید:", buttons=_rps_buttons())
        return

    game = DICE_GAMES.get(game_key)
    if game is None:
        return
    value = await _roll(event, game.emoji)
    logger.info("%s: %s", game_key, value)
    if value < game.min_win:
        await event.edit(game.lose.format(value=value) + LOSE_TAIL)
        return

    prize = random.choice(REWARDS)
    new_amount = await update_Money(user_id=user_id, Money=prize)
    await event.edit(
        _win_text(game.win_how.format(value=value), prize), buttons=_balance_button("موجودی جدید شما", new_amount)
    )
    await send_log_message(
        LogType.OTHER,
        message=f"{game.emoji} کاربر خوش‌شانس {user_id} {game.log_how.format(value=value)} و برنده مبلغ {prize:,} تومان شد! 🎉",
    )


@bot_is_offline
@debounce_callback()
async def rps_choice(event) -> None:
    choice = event.data.decode().split("_", 1)[1]
    if choice not in RPS_BEATS:
        return
    user_id = event.sender_id
    await UserCRUD().update_user(user_id=user_id, last_dice_roll=datetime.now().timestamp())

    bot_choice = random.choice(list(RPS_BEATS))
    text = (
        f"{RPS_HEADER}شما: {RPS_EMOJIS[choice]} {RPS_NAMES[choice]}\n"
        f"ربات: {RPS_EMOJIS[bot_choice]} {RPS_NAMES[bot_choice]}\n\n"
    )
    if choice == bot_choice:
        prize = RPS_TIE_PRIZE
        text += f"🤝 مساوی! جایزه تسلی {prize:,} تومان!"
    elif RPS_BEATS[choice] == bot_choice:
        prize = random.choice(REWARDS)
        text += f"🎉 تبریک! شما برنده شدید و {prize:,} تومان جایزه گرفتید!"
    else:
        await event.edit(text + "😔 متأسفانه این بار برنده نشدید! شانس خود را فردا دوباره امتحان کنید! 🍀")
        return

    new_amount = await update_Money(user_id=user_id, Money=prize)
    await event.edit(text, buttons=_balance_button("موجودی جدید", new_amount))
    await send_log_message(LogType.OTHER, message=f"✂️ کاربر {user_id} در سنگ کاغذ قیچی {prize:,} تومان برنده شد! 🎉")


def setup(ctx: PluginContext) -> None:
    ctx.add_event_handler(
        dice_shortcut, events.NewMessage(incoming=True, pattern=r"^/dice$", func=lambda e: not e.is_channel)
    )
    ctx.add_event_handler(games_command, events.NewMessage(pattern="/games"))
    ctx.add_event_handler(back_to_games, events.CallbackQuery(data=b"back_to_games"))
    ctx.add_event_handler(play_game, events.CallbackQuery(pattern=rb"game_.*"))
    ctx.add_event_handler(rps_choice, events.CallbackQuery(pattern=rb"rps_.*"))
