"""State constants for user balance."""

BALANCE_FLOW_MSG_STEP = "balance_flow_msg_id"

STEP_CART_B_CART = "cart_b_cart"
STEP_CART_B_CART_AMOUNT = "cart_b_cart_amount"
STEP_CART_B_CART2 = "cart_b_cart2"
STEP_MABLAGH_SHARJ = "mablagh_sharj"
STEP_AUTO_CARD_2 = "AutoCardToCard_2"
STEP_CRYPTO_TRX_2 = "CryptoPayments_TRX_2"
STEP_CRYPTO_USDT_2 = "CryptoPayments_USDT_2"
STEP_CRYPTO_TON_2 = "CryptoPayments_TON_2"
STEP_STARS_2 = "StarsPayment_2"
STEP_CONF_NUMBER = "conf_number"
STEP_HOME = "home"
STEP_START = "start"

BALANCE_FLOW_CANCEL_STEPS = frozenset(
    {
        STEP_CART_B_CART_AMOUNT,
        STEP_CART_B_CART2,
        STEP_MABLAGH_SHARJ,
        STEP_AUTO_CARD_2,
        STEP_CRYPTO_TRX_2,
        STEP_CRYPTO_USDT_2,
        STEP_CRYPTO_TON_2,
        STEP_STARS_2,
    }
)

LEGACY_CANCEL_MESSAGES = frozenset({"🏠", "🏠 بازگشت"})
NAV_COMMAND_PREFIXES = ("/start", "/panel")

CALLBACK_AUTO_CARD = "AutoCardToCard"
CALLBACK_CRYPTO = "CryptoPayments"
CALLBACK_CRYPTO_TRX = "CryptoPayments_TRX"
CALLBACK_CRYPTO_USDT = "CryptoPayments_USDT"
CALLBACK_CRYPTO_TON = "CryptoPayments_TON"
CALLBACK_STARS = "StarsPayment"
CALLBACK_CART_PAYMENT = "cart_payment"
CALLBACK_CART_PAYMENT_SENDPHOTO = "cart_payment_sendphoto"
CALLBACK_FLOW_CANCEL = "balance_flow_cancel"
CALLBACK_RETURN_HOME = b"balance_return_home"
CALLBACK_BACK_TO_BALANCE = "back_to_balance"
CALLBACK_DIRECT_PAY_TOPUP = "direct_pay_topup"
CALLBACK_CART_B_CART = "cart_b_cart"
CALLBACK_REFERRAL_LINK = "refrallLink"

MENU_ADD_BALANCE_TEXT = "💰 افزایش موجودی"
CHARGE_COMMAND = "/charge"
