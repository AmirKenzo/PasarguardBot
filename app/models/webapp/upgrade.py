"""WebApp DTOs: extend-time and extra-volume service upgrades, and config transfer."""

from pydantic import BaseModel, Field


class TimePlanItem(BaseModel):
    id: int
    duration_days: int
    price: int


class WebAppExtendTimeOptionsRequest(BaseModel):
    code: int = Field(..., description="Service code")
    session_token: str | None = None
    init_data: str | None = None


class WebAppExtendTimeOptionsResponse(BaseModel):
    ok: bool
    service_code: str | None = None
    panel_name: str | None = None
    plans: list[TimePlanItem] = Field(default_factory=list)
    error: str | None = None


class WebAppExtendTimeConfirmRequest(BaseModel):
    code: int = Field(..., description="Service code")
    plan_id: int = Field(..., description="Selected time plan id")
    session_token: str | None = None
    init_data: str | None = None


class WebAppExtendTimeConfirmResponse(BaseModel):
    ok: bool
    new_balance: int | None = None
    new_expiration_timestamp: int | None = None
    added_days: int | None = None
    amount_paid: int | None = None
    config_name: str | None = None
    error: str | None = None


class VolumePlanItem(BaseModel):
    id: int
    storage_gb: float
    price: int


class WebAppExtraVolumeOptionsRequest(BaseModel):
    code: int = Field(..., description="Service code")
    session_token: str | None = None
    init_data: str | None = None


class WebAppExtraVolumeOptionsResponse(BaseModel):
    ok: bool
    service_code: str | None = None
    panel_name: str | None = None
    plans: list[VolumePlanItem] = Field(default_factory=list)
    error: str | None = None


class WebAppExtraVolumeConfirmRequest(BaseModel):
    code: int = Field(..., description="Service code")
    plan_id: int = Field(..., description="Selected volume plan id")
    session_token: str | None = None
    init_data: str | None = None


class WebAppExtraVolumeConfirmResponse(BaseModel):
    ok: bool
    new_balance: int | None = None
    new_total_traffic_bytes: int | None = None
    added_bytes: int | None = None
    amount_paid: int | None = None
    config_name: str | None = None
    error: str | None = None


class WebAppTransferConfigRequest(BaseModel):
    code: int = Field(..., description="Service code")
    target_user_id: int = Field(..., description="Destination Telegram user id")
    session_token: str | None = None
    init_data: str | None = None


class WebAppTransferConfigResponse(BaseModel):
    ok: bool
    target_user_id: int | None = None
    error: str | None = None
