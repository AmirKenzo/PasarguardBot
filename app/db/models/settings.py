from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy import JSON, BigInteger, Integer, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

DEFAULT_HOME_MENU_SETTINGS: dict[str, Any] = {
    "profile_mode": True,
    "help_mode": True,
    "support_mode": True,
    "advanced_settings_mode": True,
}

DEFAULT_CORE_SETTINGS: dict[str, Any] = {
    "bot_mode": True,
    "sale_mode": False,
    "single_panel_buy_mode": False,
    "channel_lock": False,
    "backup_interval_hours": 24,
    **DEFAULT_HOME_MENU_SETTINGS,
}

DEFAULT_PAYMENT_SETTINGS: dict[str, Any] = {
    "pay_mode": False,
    "pay_phone_verify": True,
    "arz_mode": False,
    "manual_card_visibility": None,
    "manual_auto_confirm": False,
    "manual_card_random_mode": False,
    "manual_deposit_min": 50000,
    "manual_deposit_max": 2000000,
    "crypto_deposit_min": 50000,
    "crypto_deposit_max": 10000000,
    "manual_bonus_enabled": False,
    "manual_bonus_percent": 0,
    "crypto_bonus_enabled": False,
    "crypto_bonus_percent": 0,
    "arz_usd": 0,
    "arz_trx": 0,
    "arz_ton": 0,
}

DEFAULT_PURCHASE_SETTINGS: dict[str, Any] = {
    "extension_mode": False,
    "upg_mode": False,
    "tamdid_mode": False,
    "test_mode": False,
    "test_panel_id": 0,
    "test_phone_verify": True,
    "direct_pay_purchase_mode": False,
    "direct_pay_renew_mode": False,
}

DEFAULT_SERVICE_TOOLS_SETTINGS: dict[str, Any] = {
    "qr_mode": False,
    "sub_mode": False,
    "other_links_mode": False,
    "client_list_mode": False,
    "usage_chart_mode": False,
    "change_link_mode": False,
    "copy_link_mode": False,
    "transfer_config_mode": False,
    "info_mode": False,
    "del_service_mode": False,
}

DEFAULT_RESELLER_SETTINGS: dict[str, Any] = {
    "reseller_sale_mode": False,
    "reseller_min_wallet_balance": 100000,
}

SETTINGS_SECTION_DEFAULTS: dict[str, dict[str, Any]] = {
    "core_settings": DEFAULT_CORE_SETTINGS,
    "payment_settings": DEFAULT_PAYMENT_SETTINGS,
    "purchase_settings": DEFAULT_PURCHASE_SETTINGS,
    "service_tools_settings": DEFAULT_SERVICE_TOOLS_SETTINGS,
    "reseller_settings": DEFAULT_RESELLER_SETTINGS,
}

SETTINGS_SECTION_COLUMNS = tuple(SETTINGS_SECTION_DEFAULTS)

SETTING_KEY_TO_SECTION: dict[str, tuple[str, str]] = {
    key: (column, key) for column, defaults in SETTINGS_SECTION_DEFAULTS.items() for key in defaults
}

SETTINGS_CONFIG_KEYS = frozenset(SETTING_KEY_TO_SECTION)


def merge_section(raw: Any, defaults: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(defaults)
    if isinstance(raw, dict):
        merged.update(raw)
    return merged


def default_settings_sections() -> dict[str, dict[str, Any]]:
    return {column: deepcopy(defaults) for column, defaults in SETTINGS_SECTION_DEFAULTS.items()}


def resolve_settings_update_kwargs(setting: Settings | None, **kwargs: Any) -> dict[str, Any]:
    """Map flat setting keys into section JSON column updates."""
    buffers = {
        column: merge_section(getattr(setting, column, None) if setting else None, defaults)
        for column, defaults in SETTINGS_SECTION_DEFAULTS.items()
    }
    touched: set[str] = set()
    direct: dict[str, Any] = {}

    for key, value in kwargs.items():
        if key in SETTINGS_SECTION_COLUMNS:
            touched.add(key)
            if isinstance(value, dict):
                buffers[key] = merge_section(value, SETTINGS_SECTION_DEFAULTS[key])
            else:
                direct[key] = value
            continue
        mapping = SETTING_KEY_TO_SECTION.get(key)
        if not mapping:
            continue
        column, json_key = mapping
        buffers[column][json_key] = value
        touched.add(column)

    for column in touched:
        if column not in direct:
            direct[column] = buffers[column]
    return direct


class Settings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    core_settings: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        insert_default=dict,
        server_default=text("'{}'"),
    )
    payment_settings: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        insert_default=dict,
        server_default=text("'{}'"),
    )
    purchase_settings: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        insert_default=dict,
        server_default=text("'{}'"),
    )
    service_tools_settings: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        insert_default=dict,
        server_default=text("'{}'"),
    )
    reseller_settings: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        insert_default=dict,
        server_default=text("'{}'"),
    )

    def __getattr__(self, name: str) -> Any:
        mapping = SETTING_KEY_TO_SECTION.get(name)
        if mapping is None:
            raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")
        column, key = mapping
        section = object.__getattribute__(self, column)
        defaults = SETTINGS_SECTION_DEFAULTS[column]
        if isinstance(section, dict) and key in section:
            return section[key]
        return defaults[key]
