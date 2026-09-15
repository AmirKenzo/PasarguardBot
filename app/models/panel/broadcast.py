"""Admin panel DTOs: broadcast jobs."""

from pydantic import BaseModel, Field

from app.models.panel.common import PanelRequest, PanelResponse

TARGET_MODES = ("all", "active", "users_with_active_service")


class PanelBroadcastJobRow(BaseModel):
    id: int
    text: str = ""
    target_mode: str = "all"
    total_targets: int = 0
    sent_ok: int = 0
    sent_fail: int = 0
    status: str | None = None
    created_at: int | None = None
    can_pause: bool = False
    can_resume: bool = False
    can_cancel: bool = False


class PanelBroadcastResponse(PanelResponse):
    jobs: list[PanelBroadcastJobRow] = Field(default_factory=list)
    target_modes: list[str] = Field(default_factory=lambda: list(TARGET_MODES))


class PanelBroadcastSendRequest(PanelRequest):
    text: str = Field(..., min_length=1, max_length=4000)
    target_mode: str = "all"
    delay_ms: int = Field(300, ge=0, le=60000)
    batch_size: int = Field(50, ge=1, le=500)
    batch_delay_ms: int = Field(2000, ge=0, le=600000)


class PanelBroadcastJobRequest(PanelRequest):
    job_id: int
