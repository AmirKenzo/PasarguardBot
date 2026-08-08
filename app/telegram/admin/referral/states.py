"""State constants for admin referral system management."""

REFERRAL_ADMIN_CALLBACKS = frozenset(
    {
        "toggle_referral_system",
        "change_referral_reward",
        "change_referral_bonus",
        "change_referral_banner",
        "referral_stats",
        "back_to_referral_management",
    }
)

REFERRAL_USER_CALLBACKS = frozenset(
    {
        "referral_invite_friends",
        "my_referral_stats",
    }
)

REFERRAL_ADMIN_STEPS = frozenset(
    {
        "change_referral_reward",
        "change_referral_bonus",
        "change_referral_banner",
    }
)

REFERRAL_MENU_MESSAGE = "🎁 سیستم دعوت دوستان"
