"""State constants for admin referral system management."""

REFERRAL_ADMIN_CALLBACKS = frozenset(
    {
        "toggle_referral_system",
        "change_referral_reward",
        "change_referral_bonus",
        "change_referral_banner",
        "toggle_referral_reward_mode",
        "change_referral_bonus_max",
        "change_referral_bonus_percent",
        "toggle_referral_bonus_mode",
        "change_referral_percent",
        "change_referral_max",
        "toggle_referral_destination",
        "toggle_referral_withdraw",
        "toggle_referral_transfer",
        "change_referral_withdraw_min",
        "referral_pending_payouts",
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
        "change_referral_percent",
        "change_referral_max",
        "change_referral_bonus_percent",
        "change_referral_bonus_max",
        "change_referral_reward",
        "change_referral_bonus",
        "change_referral_banner",
        "change_referral_withdraw_min",
    }
)

REFERRAL_MENU_MESSAGE = "🎁 سیستم دعوت دوستان"
