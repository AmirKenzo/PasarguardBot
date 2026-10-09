"""Reseller user flow state constants."""

RESELLER_MENU_MESSAGE = "🏢 خرید پنل نمایندگی"
MY_RESELLERS_MESSAGE = "📋 نمایندگی‌های من"
RESELLER_FLOW_MSG_KEY = "reseller_flow_msg_id"

# Add-on purchase (extra days, extra volume, extra users).
STEP_ADDON_CUSTOM = "reseller_addon_custom_input"
STEP_ADDON_CONFIRM = "reseller_addon_confirm"
ADDON_CODE_KEY = "reseller_addon_code"
ADDON_TYPE_KEY = "reseller_addon_type"
ADDON_QUANTITY_KEY = "reseller_addon_quantity"

RESELLER_INPUT_STEPS = (
    "reseller_add_price",
    "reseller_add_unit_price",
    "reseller_add_volume",
    "reseller_add_max_users",
    "reseller_add_duration",
    "reseller_add_data_limit",
    "reseller_enter_volume",
    "reseller_enter_username",
    "reseller_discount_code",
    "reseller_renew_confirm",
    "reseller_renew_discount_code",
    "reseller_usage_cap_input",
)
