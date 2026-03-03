from datetime import datetime
from typing import Optional

from pydantic import Field, field_validator, model_validator

from ..base import FrigateBaseModel
from .zone import ZoneModeEnum

__all__ = [
    "AdaptiveLoadSheddingConfig",
    "DetectConfig",
    "PriorityRoutingConfig",
    "RoiMaskConfig",
    "RoiScheduleConfig",
    "RoiSchedulingConfig",
    "StationaryConfig",
    "StationaryMaxFramesConfig",
]


class AdaptiveLoadSheddingConfig(FrigateBaseModel):
    enabled: bool = Field(default=False, title="Enable adaptive load shedding.")
    queue_high_watermark: int = Field(
        default=1,
        title="Queue depth threshold to enter saturation mode.",
        ge=0,
    )
    queue_recovery_watermark: int = Field(
        default=0,
        title="Queue depth threshold to start recovery.",
        ge=0,
    )
    inference_latency_high_ms: float = Field(
        default=120.0,
        title="Inference latency threshold (ms) to enter saturation mode.",
        ge=1.0,
    )
    inference_latency_recovery_ms: float = Field(
        default=80.0,
        title="Inference latency threshold (ms) to start recovery.",
        ge=1.0,
    )
    min_skip_frames: int = Field(
        default=0,
        title="Minimum number of frames to skip between processed frames.",
        ge=0,
    )
    max_skip_frames: int = Field(
        default=4,
        title="Maximum number of frames to skip between processed frames.",
        ge=0,
    )
    recovery_stable_cycles: int = Field(
        default=12,
        title="Stable processing cycles required before decreasing skip.",
        ge=1,
    )
    critical_labels: list[str] = Field(
        default_factory=list,
        title="Labels treated as critical during saturation.",
    )
    shed_non_critical_events: bool = Field(
        default=True,
        title="Drop low-priority events while saturated.",
    )

    @model_validator(mode="after")
    def validate_thresholds(self):
        if self.max_skip_frames < self.min_skip_frames:
            raise ValueError("max_skip_frames must be greater than min_skip_frames")
        if self.queue_recovery_watermark > self.queue_high_watermark:
            raise ValueError(
                "queue_recovery_watermark must be less than or equal to queue_high_watermark"
            )
        if self.inference_latency_recovery_ms > self.inference_latency_high_ms:
            raise ValueError(
                "inference_latency_recovery_ms must be less than or equal to inference_latency_high_ms"
            )
        return self


class RoiMaskConfig(FrigateBaseModel):
    coordinates: str = Field(
        title="Polygon coordinates relative to frame as x1,y1,x2,y2,..."
    )


class RoiScheduleConfig(FrigateBaseModel):
    name: str = Field(title="ROI schedule profile name.", min_length=1)
    enabled: bool = Field(default=True, title="Enable this ROI schedule.")
    version: int = Field(
        default=1,
        title="Version of geometry/policy set for auditability.",
        ge=1,
    )
    days_of_week: list[int] = Field(
        default_factory=lambda: [0, 1, 2, 3, 4, 5, 6],
        title="Days when this profile is active (0=Monday..6=Sunday).",
    )
    start_time: str = Field(default="00:00", title="Start time HH:MM.")
    end_time: str = Field(default="23:59", title="End time HH:MM.")
    region_size_multiplier: float = Field(
        default=1.0,
        title="Region size multiplier applied to clustered ROI regions.",
        ge=0.5,
        le=2.0,
    )
    dynamic_masks: list[RoiMaskConfig] = Field(
        default_factory=list,
        title="Dynamic masks to suppress recurring noise regions.",
    )
    zone_modes: dict[str, ZoneModeEnum] = Field(
        default_factory=dict,
        title="Zone mode overrides by zone name for this period.",
    )

    @field_validator("days_of_week")
    @classmethod
    def validate_days_of_week(cls, value: list[int]):
        if not value:
            raise ValueError("days_of_week cannot be empty")
        if any(day < 0 or day > 6 for day in value):
            raise ValueError("days_of_week entries must be between 0 and 6")
        return value

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time_format(cls, value: str):
        try:
            datetime.strptime(value, "%H:%M")
        except ValueError as exc:
            raise ValueError("time must be in HH:MM format") from exc
        return value


class RoiSchedulingConfig(FrigateBaseModel):
    enabled: bool = Field(default=False, title="Enable ROI scheduling.")
    profiles: list[RoiScheduleConfig] = Field(
        default_factory=list,
        title="ROI profiles by schedule.",
    )


class PriorityRoutingConfig(FrigateBaseModel):
    enabled: bool = Field(default=False, title="Enable priority routing.")
    high_priority: bool = Field(
        default=False,
        title="Route this camera to high-priority queue.",
    )
    tenant_key: str = Field(
        default="default",
        title="Tenant key for quota isolation.",
        min_length=1,
    )
    worker_affinity_key: str | None = Field(
        default=None,
        title="Optional worker affinity key for this camera.",
    )
    max_normal_queue_depth: int = Field(
        default=32,
        title="Maximum normal queue depth before shedding low-priority requests.",
        ge=1,
    )


class StationaryMaxFramesConfig(FrigateBaseModel):
    default: Optional[int] = Field(default=None, title="Default max frames.", ge=1)
    objects: dict[str, int] = Field(
        default_factory=dict, title="Object specific max frames."
    )


class StationaryConfig(FrigateBaseModel):
    interval: Optional[int] = Field(
        default=None,
        title="Frame interval for checking stationary objects.",
        gt=0,
    )
    threshold: Optional[int] = Field(
        default=None,
        title="Number of frames without a position change for an object to be considered stationary",
        ge=1,
    )
    max_frames: StationaryMaxFramesConfig = Field(
        default_factory=StationaryMaxFramesConfig,
        title="Max frames for stationary objects.",
    )
    classifier: bool = Field(
        default=True,
        title="Enable visual classifier for determing if objects with jittery bounding boxes are stationary.",
    )


class DetectConfig(FrigateBaseModel):
    enabled: bool = Field(default=False, title="Detection Enabled.")
    height: Optional[int] = Field(
        default=None, title="Height of the stream for the detect role."
    )
    width: Optional[int] = Field(
        default=None, title="Width of the stream for the detect role."
    )
    fps: int = Field(
        default=5, title="Number of frames per second to process through detection."
    )
    min_initialized: Optional[int] = Field(
        default=None,
        title="Minimum number of consecutive hits for an object to be initialized by the tracker.",
    )
    max_disappeared: Optional[int] = Field(
        default=None,
        title="Maximum number of frames the object can disappear before detection ends.",
    )
    stationary: StationaryConfig = Field(
        default_factory=StationaryConfig,
        title="Stationary objects config.",
    )
    annotation_offset: int = Field(
        default=0, title="Milliseconds to offset detect annotations by."
    )
    adaptive_load_shedding: AdaptiveLoadSheddingConfig = Field(
        default_factory=AdaptiveLoadSheddingConfig,
        title="Adaptive frame skip and load shedding settings.",
    )
    roi_scheduling: RoiSchedulingConfig = Field(
        default_factory=RoiSchedulingConfig,
        title="Dynamic ROI profile scheduling settings.",
    )
    priority_routing: PriorityRoutingConfig = Field(
        default_factory=PriorityRoutingConfig,
        title="Priority routing and quota controls.",
    )
