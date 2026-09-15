"""Admin panel DTOs: system status, backups and bulk volume/time increase."""

from pydantic import BaseModel, Field

from app.models.panel.common import PanelRequest, PanelResponse
from app.models.panel.services import PanelPanelOption


class PanelSystemMetrics(BaseModel):
    cpu_percent: float = 0
    cpu_cores: int = 0
    ram_percent: float = 0
    ram_used: int = 0
    ram_total: int = 0
    disk_percent: float = 0
    disk_used: int = 0
    disk_total: int = 0
    python: str | None = None
    platform: str | None = None


class PanelVersions(BaseModel):
    app: str | None = None
    telethon: str | None = None
    telethon_layer: str | None = None
    fastapi: str | None = None
    pasarguard: str | None = None
    database: str | None = None


class PanelScheduledJob(BaseModel):
    id: str
    last_run: str | None = None
    next_run: str | None = None


class PanelToolsResponse(PanelResponse):
    metrics: PanelSystemMetrics = Field(default_factory=PanelSystemMetrics)
    versions: PanelVersions = Field(default_factory=PanelVersions)
    jobs: list[PanelScheduledJob] = Field(default_factory=list)
    panels: list[PanelPanelOption] = Field(default_factory=list)
    backup_supported: bool = False


class PanelBulkIncreaseRequest(PanelRequest):
    """``panel`` is a panel code, or ``all`` for every panel."""

    panel: str = "all"
    volume_gb: float | None = Field(None, gt=0)
    days: int | None = Field(None, gt=0)
    confirm: bool = False
