"""Signed referral start parameters: round trip and tamper detection."""

from app.services.billing.referral import build_referral_start_param, parse_referral_start_param


class TestReferralStartParam:
    def test_round_trip(self):
        user_id = 987654321
        param = build_referral_start_param(user_id)
        assert param.startswith("ref_")
        assert parse_referral_start_param(param) == user_id

    def test_tampered_signature_rejected(self):
        param = build_referral_start_param(12345)
        tampered = param[:-1] + ("0" if param[-1] != "0" else "1")
        assert parse_referral_start_param(tampered) is None

    def test_invalid_prefix(self):
        assert parse_referral_start_param("invite_123-abc") is None

    def test_empty_param(self):
        assert parse_referral_start_param("") is None

    def test_tampered_user_id_rejected(self):
        param = build_referral_start_param(555)
        tampered = param.replace("555", "556")
        assert parse_referral_start_param(tampered) is None
