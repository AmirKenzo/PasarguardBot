"""Crypto wallets, manual cards and card-to-card auto-approve rules."""

from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Request

from app.db.crud.cards import ManualCardManager
from app.db.crud.manual_auto_approve_rules import ManualAutoApproveRuleCRUD
from app.db.crud.settings import SettingsManager
from app.db.crud.tonpays_invoices import tonpays_stats_since
from app.db.crud.wallets import WalletCRUD
from app.db.crud.zarinpal_payments import zarinpal_stats_since
from app.db.crud.zibal_payments import zibal_stats_since
from app.models.panel.common import ActionResponse, PanelRequest
from app.models.panel.payments import (
    WALLET_TYPES,
    PanelAutoApproveRuleRow,
    PanelCardActionRequest,
    PanelCardCreateRequest,
    PanelCardRow,
    PanelPaymentsResponse,
    PanelRuleCreateRequest,
    PanelRuleDeleteRequest,
    PanelRuleToggleRequest,
    PanelTonPaysResponse,
    PanelTonPaysSaveRequest,
    PanelTonPaysStats,
    PanelTonPaysTestRequest,
    PanelWalletCreateRequest,
    PanelWalletDeleteRequest,
    PanelWalletRow,
    PanelZarinpalResponse,
    PanelZarinpalSaveRequest,
    PanelZarinpalTestRequest,
    PanelZibalResponse,
    PanelZibalSaveRequest,
    PanelZibalTestRequest,
)
from app.panel import audit
from app.routers.panel import guard
from app.routers.panel.auth import PanelActor
from app.services.billing import payment_stats
from app.services.payments import zarinpal_config, zibal_config
from app.services.payments.tonpays import test_connection
from app.services.payments.tonpays_config import (
    api_key_for,
    callback_url,
    deposit_limits,
    gateway_mode,
    is_ready,
    mask_key,
)
from app.services.payments.zarinpal import test_connection as zarinpal_test_connection
from app.services.payments.zibal import test_connection as zibal_test_connection

router = APIRouter()


async def _log(actor: PanelActor, action: str, **kwargs) -> None:
    await audit.record(
        actor_id=actor.user_id,
        actor_username=actor.username,
        action=action,
        ip=actor.ip,
        **kwargs,
    )


@router.post("/panel/payments", response_model=PanelPaymentsResponse)
async def payments_overview(payload: PanelRequest, request: Request) -> PanelPaymentsResponse:
    async def handle(_: PanelActor) -> PanelPaymentsResponse:
        wallets, cards, rules = await asyncio.gather(
            WalletCRUD().get_all_wallets(),
            ManualCardManager().get_all_cards(),
            ManualAutoApproveRuleCRUD().get_all(),
        )
        taken = {str(wallet.type).upper() for wallet in wallets}
        return PanelPaymentsResponse(
            wallets=[
                PanelWalletRow(
                    id=int(wallet.id),
                    type=wallet.type,
                    address=wallet.address,
                    has_api_key=bool(wallet.api_key),
                )
                for wallet in wallets
            ],
            available_wallet_types=[value for value in WALLET_TYPES if value not in taken],
            cards=[
                PanelCardRow(
                    id=int(card.id),
                    number=card.number,
                    name=card.name,
                    active=bool(card.active),
                )
                for card in cards
            ],
            rules=[
                PanelAutoApproveRuleRow(
                    id=int(rule.id),
                    min_successful_tx=int(rule.min_successful_tx or 0),
                    max_successful_tx=rule.max_successful_tx,
                    auto_approve_delay_minutes=int(rule.auto_approve_delay_minutes or 0),
                    is_active=bool(rule.is_active),
                )
                for rule in rules
            ],
        )

    return await guard.run(payload, request, PanelPaymentsResponse, handle)


@router.post("/panel/payments/wallets/create", response_model=ActionResponse)
async def wallet_create(payload: PanelWalletCreateRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        wallet_type = payload.wallet_type.strip().upper()
        if wallet_type not in WALLET_TYPES:
            return ActionResponse(ok=False, error="نوع ارز معتبر نیست.")
        created = await WalletCRUD().create_wallet(
            payload.address.strip(), wallet_type, payload.api_key.strip() or None
        )
        if created is None:
            return ActionResponse(ok=False, error="برای این ارز قبلاً کیف پول ثبت شده است.")
        await _log(actor, "wallet_create", target_type="wallet", target_id=wallet_type)
        return ActionResponse(message="کیف پول اضافه شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/payments/wallets/delete", response_model=ActionResponse)
async def wallet_delete(payload: PanelWalletDeleteRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        ok = await WalletCRUD().delete_wallet(payload.wallet_id)
        await _log(actor, "wallet_delete", target_type="wallet", target_id=payload.wallet_id)
        if not ok:
            return ActionResponse(ok=False, error="کیف پولی با این شناسه پیدا نشد.")
        return ActionResponse(message="کیف پول حذف شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/payments/cards/create", response_model=ActionResponse)
async def card_create(payload: PanelCardCreateRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        number = "".join(ch for ch in payload.number if ch.isdigit())
        if len(number) < 12:
            return ActionResponse(ok=False, error="شمارهٔ کارت معتبر نیست.")
        card = await ManualCardManager().add_card(number, payload.name.strip(), payload.active)
        if card is None:
            return ActionResponse(ok=False, error="کارت ثبت نشد.")
        await _log(actor, "card_create", target_type="manual_card", target_id=number[-4:])
        return ActionResponse(message="کارت اضافه شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/payments/cards/activate", response_model=ActionResponse)
async def card_activate(payload: PanelCardActionRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        ok = await ManualCardManager().set_active(payload.card_id)
        await _log(actor, "card_activate", target_type="manual_card", target_id=payload.card_id)
        if not ok:
            return ActionResponse(ok=False, error="کارتی با این شناسه پیدا نشد.")
        return ActionResponse(message="کارت فعال شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/payments/cards/delete", response_model=ActionResponse)
async def card_delete(payload: PanelCardActionRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        ok = await ManualCardManager().delete_card(payload.card_id)
        await _log(actor, "card_delete", target_type="manual_card", target_id=payload.card_id)
        if not ok:
            return ActionResponse(ok=False, error="کارتی با این شناسه پیدا نشد.")
        return ActionResponse(message="کارت حذف شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/payments/rules/create", response_model=ActionResponse)
async def rule_create(payload: PanelRuleCreateRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        maximum = payload.max_successful_tx
        if maximum is not None and maximum < payload.min_successful_tx:
            return ActionResponse(ok=False, error="حداکثر نمی‌تواند از حداقل کمتر باشد.")
        await ManualAutoApproveRuleCRUD().create(
            min_successful_tx=payload.min_successful_tx,
            max_successful_tx=maximum,
            auto_approve_delay_minutes=payload.auto_approve_delay_minutes,
        )
        await _log(
            actor,
            "auto_approve_rule_create",
            target_type="auto_approve_rule",
            detail={
                "min": payload.min_successful_tx,
                "max": maximum,
                "delay": payload.auto_approve_delay_minutes,
            },
        )
        return ActionResponse(message="قانون اضافه شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/payments/rules/toggle", response_model=ActionResponse)
async def rule_toggle(payload: PanelRuleToggleRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        updated = await ManualAutoApproveRuleCRUD().update(payload.rule_id, is_active=payload.is_active)
        await _log(actor, "auto_approve_rule_update", target_type="auto_approve_rule", target_id=payload.rule_id)
        if not updated:
            return ActionResponse(ok=False, error="قانونی با این شناسه پیدا نشد.")
        return ActionResponse(message="وضعیت قانون تغییر کرد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/payments/rules/delete", response_model=ActionResponse)
async def rule_delete(payload: PanelRuleDeleteRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        ok = await ManualAutoApproveRuleCRUD().delete(payload.rule_id)
        await _log(actor, "auto_approve_rule_delete", target_type="auto_approve_rule", target_id=payload.rule_id)
        if not ok:
            return ActionResponse(ok=False, error="قانونی با این شناسه پیدا نشد.")
        return ActionResponse(message="قانون حذف شد.")

    return await guard.run(payload, request, ActionResponse, handle)


def _start_of_today() -> int:
    return int(payment_stats.tehran_day_start().timestamp())


@router.post("/panel/payments/tonpays", response_model=PanelTonPaysResponse)
async def tonpays_overview(payload: PanelRequest, request: Request) -> PanelTonPaysResponse:
    async def handle(_: PanelActor) -> PanelTonPaysResponse:
        settings = await SettingsManager().get_settings()
        if settings is None:
            return PanelTonPaysResponse(ok=False, error="تنظیمات ربات هنوز ساخته نشده است.")
        api_key = api_key_for(settings, "standard")
        custom_key = api_key_for(settings, "custom")
        deposit_min, deposit_max = deposit_limits(settings)
        return PanelTonPaysResponse(
            enabled=bool(settings.tonpays_enabled),
            mode=gateway_mode(settings),
            api_key_masked=mask_key(api_key) if api_key else "",
            custom_key_masked=mask_key(custom_key) if custom_key else "",
            has_api_key=bool(api_key),
            has_custom_key=bool(custom_key),
            ready=is_ready(settings),
            deposit_min=deposit_min,
            deposit_max=deposit_max,
            bonus_enabled=bool(settings.tonpays_bonus_enabled),
            bonus_percent=int(settings.tonpays_bonus_percent or 0),
            webhook_url=callback_url(),
            stats=PanelTonPaysStats(**await tonpays_stats_since(_start_of_today())),
        )

    return await guard.run(payload, request, PanelTonPaysResponse, handle)


@router.post("/panel/payments/tonpays/save", response_model=ActionResponse)
async def tonpays_save(payload: PanelTonPaysSaveRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        manager = SettingsManager()
        settings = await manager.get_settings()
        if settings is None:
            return ActionResponse(ok=False, error="تنظیمات ربات هنوز ساخته نشده است.")
        updates: dict = {}
        if payload.enabled is not None:
            updates["tonpays_enabled"] = payload.enabled
        if payload.mode is not None:
            updates["tonpays_mode"] = payload.mode
        if payload.clear_api_key:
            updates["tonpays_api_key"] = ""
        elif payload.api_key.strip():
            updates["tonpays_api_key"] = payload.api_key.strip()
        if payload.clear_custom_key:
            updates["tonpays_custom_key"] = ""
        elif payload.custom_key.strip():
            updates["tonpays_custom_key"] = payload.custom_key.strip()
        current_min, current_max = deposit_limits(settings)
        new_min = payload.deposit_min if payload.deposit_min is not None else current_min
        new_max = payload.deposit_max if payload.deposit_max is not None else current_max
        if new_max < new_min:
            return ActionResponse(ok=False, error="حداکثر مبلغ باید بیشتر از حداقل باشد.")
        updates["tonpays_deposit_min"] = new_min
        updates["tonpays_deposit_max"] = new_max
        if payload.bonus_enabled is not None:
            updates["tonpays_bonus_enabled"] = payload.bonus_enabled
        if payload.bonus_percent is not None:
            updates["tonpays_bonus_percent"] = payload.bonus_percent
        await manager.update_setting(settings.id, **updates)
        await _log(
            actor,
            "tonpays_settings_update",
            target_type="settings",
            target_id="tonpays",
            detail={key: value for key, value in updates.items() if not key.endswith("_key")},
        )
        return ActionResponse(message="تنظیمات TonPays ذخیره شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/payments/tonpays/test", response_model=ActionResponse)
async def tonpays_test(payload: PanelTonPaysTestRequest, request: Request) -> ActionResponse:
    async def handle(_: PanelActor) -> ActionResponse:
        key = payload.api_key.strip()
        if not key:
            settings = await SettingsManager().get_settings()
            key = api_key_for(settings, payload.mode) if settings else ""
        if not key:
            return ActionResponse(ok=False, error="کلید این نوع درگاه ثبت نشده است.")
        started = time.monotonic()
        ok, message = await test_connection(key, payload.mode)
        elapsed = int((time.monotonic() - started) * 1000)
        return ActionResponse(ok=ok, message=f"{message} ({elapsed}ms)" if ok else None, error=None if ok else message)

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/payments/zarinpal", response_model=PanelZarinpalResponse)
async def zarinpal_overview(payload: PanelRequest, request: Request) -> PanelZarinpalResponse:
    async def handle(_: PanelActor) -> PanelZarinpalResponse:
        settings = await SettingsManager().get_settings()
        if settings is None:
            return PanelZarinpalResponse(ok=False, error="تنظیمات ربات هنوز ساخته نشده است.")
        merchant = zarinpal_config.stored_merchant_id(settings)
        deposit_min, deposit_max = zarinpal_config.deposit_limits(settings)
        return PanelZarinpalResponse(
            enabled=bool(settings.zarinpal_enabled),
            sandbox=zarinpal_config.is_sandbox(settings),
            merchant_masked=zarinpal_config.mask_merchant(merchant),
            has_merchant=bool(merchant),
            ready=zarinpal_config.is_ready(settings),
            deposit_min=deposit_min,
            deposit_max=deposit_max,
            bonus_enabled=bool(settings.zarinpal_bonus_enabled),
            bonus_percent=int(settings.zarinpal_bonus_percent or 0),
            callback_url=zarinpal_config.callback_url(),
            stats=PanelTonPaysStats(**await zarinpal_stats_since(_start_of_today())),
        )

    return await guard.run(payload, request, PanelZarinpalResponse, handle)


@router.post("/panel/payments/zarinpal/save", response_model=ActionResponse)
async def zarinpal_save(payload: PanelZarinpalSaveRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        manager = SettingsManager()
        settings = await manager.get_settings()
        if settings is None:
            return ActionResponse(ok=False, error="تنظیمات ربات هنوز ساخته نشده است.")
        updates: dict = {}
        if payload.enabled is not None:
            updates["zarinpal_enabled"] = payload.enabled
        merchant = zarinpal_config.stored_merchant_id(settings)
        if payload.clear_merchant:
            merchant = ""
            updates["zarinpal_merchant_id"] = ""
        elif payload.merchant_id.strip():
            merchant = payload.merchant_id.strip()
            if not zarinpal_config.is_valid_merchant_id(merchant):
                return ActionResponse(ok=False, error="مرچنت کد باید ۳۶ کاراکتر به شکل UUID باشد.")
            updates["zarinpal_merchant_id"] = merchant
        sandbox = payload.sandbox if payload.sandbox is not None else zarinpal_config.is_sandbox(settings)
        if not sandbox and not zarinpal_config.is_valid_merchant_id(merchant):
            return ActionResponse(ok=False, error="برای حالت واقعی، اول مرچنت کد معتبر ثبت کنید.")
        updates["zarinpal_sandbox"] = sandbox
        current_min, current_max = zarinpal_config.deposit_limits(settings)
        new_min = payload.deposit_min if payload.deposit_min is not None else current_min
        new_max = payload.deposit_max if payload.deposit_max is not None else current_max
        if new_max < new_min:
            return ActionResponse(ok=False, error="حداکثر مبلغ باید بیشتر از حداقل باشد.")
        updates["zarinpal_deposit_min"] = new_min
        updates["zarinpal_deposit_max"] = new_max
        if payload.bonus_enabled is not None:
            updates["zarinpal_bonus_enabled"] = payload.bonus_enabled
        if payload.bonus_percent is not None:
            updates["zarinpal_bonus_percent"] = payload.bonus_percent
        await manager.update_setting(settings.id, **updates)
        await _log(
            actor,
            "zarinpal_settings_update",
            target_type="settings",
            target_id="zarinpal",
            detail={key: value for key, value in updates.items() if key != "zarinpal_merchant_id"},
        )
        return ActionResponse(message="تنظیمات زرین‌پال ذخیره شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/payments/zarinpal/test", response_model=ActionResponse)
async def zarinpal_test(payload: PanelZarinpalTestRequest, request: Request) -> ActionResponse:
    async def handle(_: PanelActor) -> ActionResponse:
        merchant = payload.merchant_id.strip()
        if merchant and not zarinpal_config.is_valid_merchant_id(merchant):
            return ActionResponse(ok=False, error="مرچنت کد باید ۳۶ کاراکتر به شکل UUID باشد.")
        if not merchant:
            settings = await SettingsManager().get_settings()
            merchant = zarinpal_config.merchant_id_for(settings, payload.sandbox) if settings else ""
        if not merchant:
            return ActionResponse(ok=False, error="مرچنت کد ثبت نشده است.")
        started = time.monotonic()
        ok, message = await zarinpal_test_connection(merchant, payload.sandbox)
        elapsed = int((time.monotonic() - started) * 1000)
        return ActionResponse(ok=ok, message=f"{message} ({elapsed}ms)" if ok else None, error=None if ok else message)

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/payments/zibal", response_model=PanelZibalResponse)
async def zibal_overview(payload: PanelRequest, request: Request) -> PanelZibalResponse:
    async def handle(_: PanelActor) -> PanelZibalResponse:
        settings = await SettingsManager().get_settings()
        if settings is None:
            return PanelZibalResponse(ok=False, error="تنظیمات ربات هنوز ساخته نشده است.")
        merchant = zibal_config.stored_merchant(settings)
        deposit_min, deposit_max = zibal_config.deposit_limits(settings)
        return PanelZibalResponse(
            enabled=bool(settings.zibal_enabled),
            sandbox=zibal_config.is_sandbox(settings),
            merchant_masked=zibal_config.mask_merchant(merchant),
            has_merchant=bool(merchant),
            ready=zibal_config.is_ready(settings),
            deposit_min=deposit_min,
            deposit_max=deposit_max,
            bonus_enabled=bool(settings.zibal_bonus_enabled),
            bonus_percent=int(settings.zibal_bonus_percent or 0),
            callback_url=zibal_config.callback_url(),
            stats=PanelTonPaysStats(**await zibal_stats_since(_start_of_today())),
        )

    return await guard.run(payload, request, PanelZibalResponse, handle)


@router.post("/panel/payments/zibal/save", response_model=ActionResponse)
async def zibal_save(payload: PanelZibalSaveRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        manager = SettingsManager()
        settings = await manager.get_settings()
        if settings is None:
            return ActionResponse(ok=False, error="تنظیمات ربات هنوز ساخته نشده است.")
        updates: dict = {}
        if payload.enabled is not None:
            updates["zibal_enabled"] = payload.enabled
        merchant = zibal_config.stored_merchant(settings)
        if payload.clear_merchant:
            merchant = ""
            updates["zibal_merchant"] = ""
        elif payload.merchant.strip():
            merchant = payload.merchant.strip()
            if not zibal_config.is_valid_merchant(merchant):
                return ActionResponse(ok=False, error="مرچنت زیبال نامعتبر است.")
            updates["zibal_merchant"] = merchant
        sandbox = payload.sandbox if payload.sandbox is not None else zibal_config.is_sandbox(settings)
        if not sandbox and not zibal_config.is_valid_merchant(merchant):
            return ActionResponse(ok=False, error="برای حالت واقعی، اول مرچنت زیبال را ثبت کنید.")
        updates["zibal_sandbox"] = sandbox
        current_min, current_max = zibal_config.deposit_limits(settings)
        new_min = payload.deposit_min if payload.deposit_min is not None else current_min
        new_max = payload.deposit_max if payload.deposit_max is not None else current_max
        if new_max < new_min:
            return ActionResponse(ok=False, error="حداکثر مبلغ باید بیشتر از حداقل باشد.")
        updates["zibal_deposit_min"] = new_min
        updates["zibal_deposit_max"] = new_max
        if payload.bonus_enabled is not None:
            updates["zibal_bonus_enabled"] = payload.bonus_enabled
        if payload.bonus_percent is not None:
            updates["zibal_bonus_percent"] = payload.bonus_percent
        await manager.update_setting(settings.id, **updates)
        await _log(
            actor,
            "zibal_settings_update",
            target_type="settings",
            target_id="zibal",
            detail={key: value for key, value in updates.items() if key != "zibal_merchant"},
        )
        return ActionResponse(message="تنظیمات زیبال ذخیره شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/payments/zibal/test", response_model=ActionResponse)
async def zibal_test(payload: PanelZibalTestRequest, request: Request) -> ActionResponse:
    async def handle(_: PanelActor) -> ActionResponse:
        merchant = payload.merchant.strip()
        if payload.sandbox:
            merchant = zibal_config.SANDBOX_MERCHANT
        elif merchant and not zibal_config.is_valid_merchant(merchant):
            return ActionResponse(ok=False, error="مرچنت زیبال نامعتبر است.")
        if not merchant:
            settings = await SettingsManager().get_settings()
            merchant = zibal_config.merchant_for(settings, False) if settings else ""
        if not merchant:
            return ActionResponse(ok=False, error="مرچنت زیبال ثبت نشده است.")
        started = time.monotonic()
        ok, message = await zibal_test_connection(merchant)
        elapsed = int((time.monotonic() - started) * 1000)
        return ActionResponse(ok=ok, message=f"{message} ({elapsed}ms)" if ok else None, error=None if ok else message)

    return await guard.run(payload, request, ActionResponse, handle)
