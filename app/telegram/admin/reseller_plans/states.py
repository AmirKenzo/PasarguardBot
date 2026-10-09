"""Admin reseller plan wizard state constants."""

from app.services.reseller.plan_rules import CREATABLE_MODES
from app.telegram.shared.reseller_plan_guides import MODE_ICONS, MODE_NAMES

RESELLER_PLAN_MENU_MESSAGE = "🏢 پلن نمایندگی"

# One step per wizard: the field being asked is kept in ``FIELD_KEY``.
STEP_ADD_FIELD = "reseller_plan_add_field"
STEP_EDIT_FIELD = "reseller_plan_edit_field"

ADMIN_INPUT_STEPS = (
    STEP_ADD_FIELD,
    STEP_EDIT_FIELD,
    "reseller_plan_edit_btn_text",
    "reseller_plan_edit_btn_icon",
    "reseller_import_username",
    "reseller_import_telegram_id",
)

# Wizard data keys.
PANEL_KEY = "reseller_plan_panel"
ROLE_ID_KEY = "reseller_plan_role_id"
ROLE_NAME_KEY = "reseller_plan_role_name"
MODE_KEY = "reseller_plan_mode"
FIELD_KEY = "reseller_plan_field"
VALUE_KEY_PREFIX = "reseller_plan_v_"
EDIT_PLAN_KEY = "reseller_edit_plan_id"
EDIT_FIELD_KEY = "reseller_edit_field"

# Type picker labels: exactly the names used everywhere else in the bot.
PRICING_MODE_LABELS = {mode: f"{MODE_ICONS.get(mode, '')} {MODE_NAMES[mode]}".strip() for mode in CREATABLE_MODES}
