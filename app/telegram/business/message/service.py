"""Admin command handlers for slim Telegram Business."""

from __future__ import annotations

from datetime import datetime

from telethon.tl import types

from app.db.crud.user import UserCRUD
from app.telegram.business.message import texts
from app.utils.network.ip_info import get_ip_info, is_valid_domain, is_valid_ip, ping_ip


async def handle_admin_commands(
    bm,
    event: types.UpdateBotNewBusinessMessage,
    msg: str,
    sender_id: int | None,
) -> bool:
    del sender_id  # reserved for future audit logging
    if msg == "id":
        user_id = event.message.peer_id.user_id
        await bm.edit_message(texts.user_id_text(user_id))
        return True

    if msg == "admin":
        await bm.edit_message(texts.ADMIN_HELP_TEXT)
        return True

    if msg.startswith("add ") or msg.startswith("+ "):
        await _handle_balance_change(bm, event, msg, positive=True)
        return True

    if msg.startswith("remove ") or msg.startswith("- "):
        await _handle_balance_change(bm, event, msg, positive=False)
        return True

    if msg.startswith("info ") or msg == "info":
        await _handle_info_command(bm, event, msg)
        return True

    if msg.startswith("ip ") or msg.startswith("ping "):
        await _handle_ip_command(bm, msg)
        return True

    return False


def _parse_user_amount(msg: str, event, *, prefix: str, alt_prefix: str):
    if msg.startswith(prefix):
        parts = msg.replace(prefix, "").strip().split()
    elif msg.startswith(alt_prefix):
        parts = msg.replace(alt_prefix, "").strip().split()
    else:
        parts = []

    if len(parts) == 1:
        return event.message.peer_id.user_id, int(parts[0])
    if len(parts) == 2:
        return int(parts[0]), int(parts[1])
    return None, None


async def _handle_balance_change(bm, event, msg: str, *, positive: bool) -> None:
    try:
        if positive:
            user_id, amount = _parse_user_amount(msg, event, prefix="add ", alt_prefix="+ ")
            format_error = texts.ADD_FORMAT_ERROR
        else:
            user_id, amount = _parse_user_amount(msg, event, prefix="remove ", alt_prefix="- ")
            format_error = texts.REMOVE_FORMAT_ERROR

        if user_id is None or amount is None:
            await bm.edit_message(format_error)
            return

        user_crud = UserCRUD()
        user = await user_crud.read_user(user_id)
        if not user:
            await bm.edit_message(texts.USER_NOT_FOUND_ERROR.format(user_id=user_id))
            return

        old_balance = int(user.amount or 0)
        delta = amount if positive else -amount
        new_balance = await user_crud.Add_Money(user_id, delta)

        if new_balance is None:
            await bm.edit_message(texts.USER_NOT_FOUND_ERROR.format(user_id=user_id))
            return

        if not positive and int(new_balance) < 0:
            await user_crud.Add_Money(user_id, amount)
            await bm.edit_message(texts.insufficient_balance_text(old_balance=old_balance, amount=amount))
            return

        if positive:
            await bm.edit_message(
                texts.balance_added_text(
                    user_id=user_id,
                    old_balance=old_balance,
                    amount=amount,
                    new_balance=int(new_balance),
                )
            )
        else:
            await bm.edit_message(
                texts.balance_removed_text(
                    user_id=user_id,
                    old_balance=old_balance,
                    amount=amount,
                    new_balance=int(new_balance),
                )
            )
    except ValueError, TypeError:
        await bm.edit_message(texts.ADD_NUMERIC_ERROR if positive else texts.REMOVE_NUMERIC_ERROR)
    except Exception as e:
        await bm.edit_message(texts.generic_error_text(str(e)))


async def _handle_info_command(bm, event, msg: str) -> None:
    try:
        if msg == "info":
            user_id = event.message.peer_id.user_id
        else:
            user_id_str = msg.replace("info ", "").strip()
            user_id = event.message.peer_id.user_id if not user_id_str else int(user_id_str)

        user_crud = UserCRUD()
        user = await user_crud.read_user(user_id)
        if not user:
            await bm.edit_message(texts.USER_NOT_FOUND_ERROR.format(user_id=user_id))
            return

        join_date = (
            datetime.fromtimestamp(user.time_s).strftime("%Y/%m/%d %H:%M")
            if getattr(user, "time_s", None)
            else "نامشخص"
        )

        lines = [
            f"👤 شناسه کاربر: {user.id} | [پروفایل کاربر](tg://user?id={user.id})",
            f"⏱️ زمان عضویت: {join_date}",
        ]

        if hasattr(user, "number"):
            lines.append(f"🔢 شماره تلفن: {user.number or 'ثبت نشده'}")

        lines.append(f"💰 موجودی: {int(user.amount or 0):,} تومان")

        if hasattr(user, "invite"):
            lines.append(f"👥 تعداد دعوت ها: {user.invite or 0}")
        if hasattr(user, "safe"):
            lines.append(f"🛡️ امن: {'فعال' if user.safe else 'غیرفعال'}")

        # Optional transaction stats — skip entirely if CRUD/method missing
        try:
            from app.db.crud.transactions import TransactionCRUD

            transaction_crud = TransactionCRUD()
            if hasattr(transaction_crud, "get_user_transaction_stats"):
                manual_stats = await transaction_crud.get_user_transaction_stats(user_id, "manual")
                auto_stats = await transaction_crud.get_user_transaction_stats(user_id, "auto")
                total_purchases = int(manual_stats.get("count", 0)) + int(auto_stats.get("count", 0))
                total_amount_spent = int(manual_stats.get("total_amount", 0)) + int(auto_stats.get("total_amount", 0))
                lines.append("")
                lines.append("📊 آمار تراکنش‌ها:")
                if int(manual_stats.get("count", 0)) > 0:
                    lines.append(
                        f"💳 کارت به کارت دستی: {manual_stats['count']} عدد - {manual_stats['total_amount']:,} تومان"
                    )
                lines.append(f"🛒 مجموع خرید موفق: {total_purchases} عدد")
                lines.append(f"💳 مجموع مبلغ خرید شده: {total_amount_spent:,} تومان")
        except Exception:
            pass

        # Optional services block
        try:
            from app.db.crud.services import ServiceCRUD

            service_crud = ServiceCRUD()
            if hasattr(service_crud, "get_services_reverse"):
                user_services = await service_crud.get_services_reverse(user_id)
                active_services = [s for s in user_services if getattr(s, "enable", False)]
                total_volume = sum(getattr(s, "package_size", 0) or 0 for s in user_services)
                total_volume_gb = total_volume / (1024**3) if total_volume else 0
                lines.append("")
                lines.append(f"📦 تعداد کل سرویس‌ها: {len(user_services)}")
                lines.append(f"✅ سرویس‌های فعال: {len(active_services)}")
                lines.append(f"📊 مجموع حجم سرویس‌ها: {total_volume_gb:.2f} گیگابایت")
        except Exception:
            pass

        if getattr(user, "ref", None):
            ref_user = await user_crud.read_user(user.ref)
            lines.append(f"👤 ارجاع دهنده: {f'`{ref_user.id}`' if ref_user else 'ندارد'}")
        elif hasattr(user, "ref"):
            lines.append("👤 ارجاع دهنده: ندارد")

        if hasattr(user, "language"):
            lines.append(f"🌐 زبان: {'فارسی' if user.language == 'fa' else 'انگلیسی'}")
        if hasattr(user, "tested"):
            lines.append(f"🧪 وضعیت تست: {'تست شده' if user.tested else 'تست نشده'}")

        await bm.edit_message("\n".join(lines))
    except ValueError, TypeError:
        await bm.edit_message(texts.INFO_ID_ERROR)
    except Exception as e:
        await bm.edit_message(texts.generic_error_text(str(e)))


async def _handle_ip_command(bm, msg: str) -> None:
    try:
        ip_or_domain = msg.replace("ip ", "").replace("ping ", "").strip()
        if not ip_or_domain:
            await bm.edit_message(texts.IP_EMPTY_ERROR)
            return

        await bm.edit_message(f"🔍 **در حال بررسی IP/دامنه...**\n\n`{ip_or_domain}`")
        if not (is_valid_ip(ip_or_domain) or is_valid_domain(ip_or_domain)):
            await bm.edit_message(texts.IP_INVALID_ERROR)
            return

        ip_data, error = await get_ip_info(ip_or_domain)
        if error:
            await bm.edit_message(texts.generic_error_text(error))
            return
        if not ip_data:
            await bm.edit_message(texts.IP_NOT_FOUND)
            return

        query_ip = ip_data.get("query", ip_or_domain)
        country = ip_data.get("country", "نامشخص")
        country_code = ip_data.get("countryCode", "N/A")
        region = ip_data.get("regionName", "نامشخص")
        city = ip_data.get("city", "نامشخص")
        isp = ip_data.get("isp", "نامشخص")
        org = ip_data.get("org", "نامشخص")
        asn = ip_data.get("as", "نامشخص")
        asname = ip_data.get("asname", "نامشخص")
        timezone = ip_data.get("timezone", "نامشخص")
        lat = ip_data.get("lat", 0)
        lon = ip_data.get("lon", 0)
        is_mobile = ip_data.get("mobile", False)
        is_proxy = ip_data.get("proxy", False)
        is_hosting = ip_data.get("hosting", False)
        reverse = ip_data.get("reverse", "نامشخص")

        await bm.edit_message(f"🔍 **در حال بررسی IP/دامنه...**\n\n`{ip_or_domain}`\n\n⏳ در حال پینگ...")
        ping_success, ping_result = await ping_ip(query_ip)
        ping_status = "🟢 آنلاین" if ping_success else "🔴 آفلاین"

        info_text = "🌐 **اطلاعات IP/دامنه**\n\n"
        info_text += f"`{msg}`\n"
        info_text += f"📍 **IP:** `{query_ip}`\n"
        if reverse and reverse != "نامشخص":
            info_text += f"🔗 **Reverse DNS:** `{reverse}`\n"
        info_text += "\n"
        info_text += "🌍 **موقعیت جغرافیایی:**\n"
        info_text += f"• کشور: `{country} ({country_code})`\n"
        info_text += f"• استان/منطقه: `{region}`\n"
        info_text += f"• شهر: `{city}`\n"
        info_text += f"• منطقه زمانی: `{timezone}`\n"
        if lat and lon:
            info_text += f"• مختصات: `{lat}, {lon}`\n"
        info_text += "\n"
        info_text += "🏢 **اطلاعات شبکه:**\n"
        info_text += f"• ISP: `{isp}`\n"
        if org and org != isp:
            info_text += f"• سازمان: `{org}`\n"
        if asn != "نامشخص":
            info_text += f"• ASN: `{asn}`\n"
        if asname and asname != "نامشخص":
            info_text += f"• AS Name: `{asname}`\n"
        info_text += "\n"
        info_text += "📊 **وضعیت:**\n"
        info_text += f"• پینگ: {ping_status}\n"
        if ping_success:
            info_text += f"• جزئیات: `{ping_result}`\n"
        info_text += f"• موبایل: `{'بله' if is_mobile else 'خیر'}`\n"
        info_text += f"• پروکسی: `{'بله' if is_proxy else 'خیر'}`\n"
        info_text += f"• هاستینگ: `{'بله' if is_hosting else 'خیر'}`\n"
        await bm.edit_message(info_text)
    except Exception as e:
        await bm.edit_message(texts.generic_error_text(str(e)))
