"""Admin panel DTOs: discount codes and the referral programme."""

from pydantic import BaseModel, Field

from app.models.panel.common import PagedRequest, PageMeta, PanelRequest, PanelResponse

CODE_PATTERN = r"^[A-Za-z0-9_\-]{2,40}$"


class PanelDiscountRow(BaseModel):
    id: int
    code: str
    discount_percentage: int = 0
    usage_limit: int = 0
    times_used: int = 0
    expiration_date: int | None = None
    user_id: int | None = None
    is_public: bool = True
    expired: bool = False
    exhausted: bool = False


class PanelDiscountsRequest(PagedRequest):
    pass


class PanelDiscountsResponse(PanelResponse):
    discounts: list[PanelDiscountRow] = Field(default_factory=list)
    meta: PageMeta = Field(default_factory=PageMeta)


class PanelDiscountSaveRequest(PanelRequest):
    """Create when ``code_id`` is null, otherwise update that code."""

    code_id: int | None = None
    code: str = Field(..., pattern=CODE_PATTERN)
    discount_percentage: int = Field(..., ge=1, le=100)
    usage_limit: int = Field(1, ge=1)
    expires_days: int | None = Field(None, ge=0, description="Null means no expiry")
    user_id: int | None = Field(None, description="Null means the code is public")
    is_public: bool = True


class PanelDiscountDeleteRequest(PanelRequest):
    code_id: int


class PanelReferralSettings(BaseModel):
    referral_enabled: bool = True
    referral_reward_amount: int = 0
    referral_bonus_amount: int = 0
    referral_banner_text: str | None = None


class PanelReferralRewardRow(BaseModel):
    id: int
    referrer_id: int | None = None
    referred_id: int | None = None
    reward_amount: int = 0
    bonus_amount: int = 0
    status: str | None = None
    created_at: int | None = None


class PanelReferralRequest(PagedRequest):
    pass


class PanelReferralResponse(PanelResponse):
    settings: PanelReferralSettings = Field(default_factory=PanelReferralSettings)
    rewards: list[PanelReferralRewardRow] = Field(default_factory=list)
    meta: PageMeta = Field(default_factory=PageMeta)
    total_rewarded: int = 0
    total_paid: int = 0
    total_bonus: int = 0


class PanelReferralSaveRequest(PanelRequest):
    referral_enabled: bool = True
    referral_reward_amount: int = Field(0, ge=0)
    referral_bonus_amount: int = Field(0, ge=0)
    referral_banner_text: str = Field("", max_length=4096)
