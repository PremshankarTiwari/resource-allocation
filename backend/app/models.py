"""Domain model for field-service dispatch.

Domain: a team of field technicians maintains industrial sites (wind farms,
substations, plants). Each day, maintenance and repair jobs arrive. Each job
needs certain skills, must be started inside a customer time window, and has a
priority. Technicians start from a home base, work a shift, and can do several
jobs in a day, travelling between sites.

Times are minutes after midnight (e.g. 480 = 08:00) to keep arithmetic simple.
"""
from __future__ import annotations

from enum import IntEnum

from pydantic import BaseModel, Field, model_validator


class Priority(IntEnum):
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class Location(BaseModel):
    lat: float
    lon: float


class Technician(BaseModel):
    """A resource: a technician with skills, a home base and a shift."""

    id: str
    name: str
    home: Location
    skills: list[str]
    shift_start: int = Field(ge=0, le=1440)
    shift_end: int = Field(ge=0, le=1440)
    max_jobs: int = Field(default=6, ge=1)

    @model_validator(mode="after")
    def _check_shift(self) -> "Technician":
        if self.shift_end <= self.shift_start:
            raise ValueError(f"{self.id}: shift_end must be after shift_start")
        return self


class Job(BaseModel):
    """A request: work at a site that needs skills and a time window."""

    id: str
    site: str
    location: Location
    required_skills: list[str]
    window_start: int = Field(ge=0, le=1440)
    window_end: int = Field(ge=0, le=1440)
    duration: int = Field(gt=0, description="On-site work time in minutes")
    priority: Priority = Priority.NORMAL

    @model_validator(mode="after")
    def _check_window(self) -> "Job":
        if self.window_end < self.window_start:
            raise ValueError(f"{self.id}: window_end must not be before window_start")
        return self


class Weights(BaseModel):
    """Soft-constraint weights. Hard constraints are never traded off."""

    travel_km: float = Field(default=1.0, ge=0, description="Cost per km driven")
    idle_minute: float = Field(default=0.2, ge=0, description="Cost per minute waiting for a window")
    overqualified_skill: float = Field(default=3.0, ge=0, description="Cost per unused skill (keep specialists free)")
    # Reward for serving a job, by priority. Unserved jobs forfeit their reward,
    # so this is what makes coverage of critical work dominate travel savings.
    reward_normal: float = Field(default=150, ge=0)
    reward_high: float = Field(default=400, ge=0)
    reward_critical: float = Field(default=1000, ge=0)

    def reward(self, priority: Priority) -> float:
        return {
            Priority.NORMAL: self.reward_normal,
            Priority.HIGH: self.reward_high,
            Priority.CRITICAL: self.reward_critical,
        }[Priority(priority)]


class Scenario(BaseModel):
    technicians: list[Technician]
    jobs: list[Job]
    speed_kmh: float = Field(default=50, gt=0, description="Average driving speed")
    road_factor: float = Field(default=1.3, ge=1, description="Road distance / straight-line distance")


class Stop(BaseModel):
    """One job in a technician's route, with computed timing."""

    job_id: str
    arrival: int
    start: int
    end: int
    travel_km: float
    wait: int


class Explanation(BaseModel):
    job_id: str
    assigned_to: str | None
    summary: str
    cost: float | None = None
    runner_up: str | None = None
    runner_up_cost: float | None = None
    rejected: dict[str, int] = Field(default_factory=dict, description="Why other technicians could not take it")


class Assignment(BaseModel):
    job_id: str
    technician_id: str
    sequence: int
    arrival: int
    start: int
    end: int
    travel_km: float


class Route(BaseModel):
    technician_id: str
    stops: list[Stop]
    return_km: float


class Metrics(BaseModel):
    jobs_total: int
    jobs_assigned: int
    coverage_pct: float
    critical_coverage_pct: float
    priority_weighted_coverage_pct: float
    total_travel_km: float
    travel_km_per_job: float
    avg_wait_min: float
    utilization_pct: float
    workload_std: float
    objective: float
    runtime_ms: float


class Solution(BaseModel):
    algorithm: str
    assignments: list[Assignment]
    routes: list[Route]
    unassigned: list[str]
    explanations: list[Explanation]
    metrics: Metrics
