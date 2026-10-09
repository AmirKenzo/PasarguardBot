"""State constants for admin manage_user."""

STEP_PANEL = "panel"
STEP_MTO_USER = "MToUser"
STEP_MTO_USER_INFO = "MToUserInfo"
STEP_ADMIN_ENTER_USERNAME = "admin_enter_username"
STEP_CREATE_CONFIG_GB = "CreateConfigFor_GB"
STEP_GB_CONFIG = "GBConfig"
STEP_TIME_CONFIG = "TimeConfig"
STEP_ADMIN_CONFIG_VOLUME_INPUT = "AdminConfigVolumeInput"
STEP_ADMIN_CONFIG_TIME_INPUT = "AdminConfigTimeInput"
STEP_ADMIN_BULK_DELETE = "AdminBulkDeleteConfigs"
STEP_ADMIN_SEARCH_CONFIG = "AdminSearchConfig"
STEP_CONFIRM_USER_PHONE = "confirmUserPhone"
ADMIN_SERVICE_LIST_PREFIX = "BackToServiceListAdmin"

# Admin repair tools on one reseller account that take a typed value.
STEP_ADMIN_RESELLER_TOOL = "AdminResellerToolInput"
RESELLER_TOOL_USER_KEY = "AdminResellerToolUserId"
RESELLER_TOOL_CODE_KEY = "AdminResellerToolCode"
RESELLER_TOOL_KIND_KEY = "AdminResellerToolKind"
RESELLER_TOOL_KINDS = ("volume_set", "volume_add", "days", "maxusers")

MANAGE_USER_SERVICE_CALLBACK_PREFIXES = (
    "DeleteServiceAdmin:",
    "DeleteServiceAdmin_confirm:",
    "service_info_admin:",
    "AdminConfigToggle:",
    "AdminConfigVolumeCustom:",
    "AdminConfigVolume:",
    "AdminConfigTimeCustom:",
    "AdminConfigTime:",
    "CreateConfigFor:",
    "MakeConfig:",
)
