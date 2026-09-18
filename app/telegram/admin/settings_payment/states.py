"""State constants for admin settings_payment."""

SETTINGS_CARD_TO_CARD_STEP = "SettingsCardToCard"

ADD_CARD_NUMBER_STEP = "add_card_number"
ADD_CARD_NAME_STEP = "add_card_name"

SET_MANUAL_MIN_STEP = "set_manual_min"
SET_MANUAL_MAX_STEP = "set_manual_max"
SET_CRYPTO_MIN_STEP = "set_crypto_min"
SET_CRYPTO_MAX_STEP = "set_crypto_max"
SET_RESELLER_MIN_WALLET_STEP = "set_reseller_min_wallet"

SET_MANUAL_BONUS_PERCENT_STEP = "set_manual_bonus_percent"
SET_CRYPTO_BONUS_PERCENT_STEP = "set_crypto_bonus_percent"
SET_STARS_BONUS_PERCENT_STEP = "set_stars_bonus_percent"

MAAR_ADD_MIN_STEP = "maar_add_min"
MAAR_ADD_MAX_STEP = "maar_add_max"
MAAR_ADD_DELAY_STEP = "maar_add_delay"
MAAR_EDIT_STEPS = frozenset({"maar_edit_min", "maar_edit_max", "maar_edit_delay"})

PAYMENT_INPUT_STEPS = frozenset(
    {
        ADD_CARD_NUMBER_STEP,
        ADD_CARD_NAME_STEP,
        SET_MANUAL_MIN_STEP,
        SET_MANUAL_MAX_STEP,
        SET_CRYPTO_MIN_STEP,
        SET_CRYPTO_MAX_STEP,
        SET_RESELLER_MIN_WALLET_STEP,
        SET_MANUAL_BONUS_PERCENT_STEP,
        SET_CRYPTO_BONUS_PERCENT_STEP,
        MAAR_ADD_MIN_STEP,
        MAAR_ADD_MAX_STEP,
        MAAR_ADD_DELAY_STEP,
        *MAAR_EDIT_STEPS,
    }
)
