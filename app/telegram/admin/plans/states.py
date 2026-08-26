"""State constants for admin plans."""

PLAN_MENU_MESSAGE = "🗞 ساخت پلن"
PANEL_STEP = "panel"

ADD_PLAN_STEPS = frozenset({"addPlan_1", "addPlan_2", "addPlan_3", "addPlan_4"})
EDIT_PLAN_STEPS = frozenset({"edit_price", "edit_storage", "edit_duration", "edit_ip_limit"})
# Custom/premium emoji sent from the sticker-style emoji tray arrives as a media
# message with no text, so these steps must accept messages without `msg`.
ICON_STEPS = frozenset({"duration_btn_set_icon", "plan_btn_set_icon"})
PLAN_INPUT_STEPS = ADD_PLAN_STEPS | EDIT_PLAN_STEPS | frozenset({"bulk_update_plans"}) | ICON_STEPS

PLAN_MAIN_MENU_CALLBACKS = frozenset(
    {
        "PlanAddSelectPanel",
        "PlanManageSelectPanel",
        "DataCancelPlans",
        "BackToPlanMainMenu",
        "CancelBulkUpdatePlans",
    }
)

PANEL_LIMIT = 20
