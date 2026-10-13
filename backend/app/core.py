"""Shared routing and constraint logic.

Every algorithm uses the same feasibility rules and the same cost function, so
the comparison between algorithms measures decision-making only.

Hard constraints (never violated):
  1. Skills: the technician has every skill the job requires.
  2. Time window: work starts no later than the job's window_end.
  3. Shift: the technician leaves home no earlier than shift_start and is back
     home by shift_end.
  4. Capacity: at most max_jobs jobs per technician.

Soft constraints (weighted in the cost):
  - kilometres driven
  - idle minutes spent waiting for a window to open
  - "over-qualification": sending a specialist to a job that does not need
    their extra skills, which can leave a later specialist job uncovered
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .models import Job, Scenario, Technician, Weights

EARTH_RADIUS_KM = 6371.0

# Reason codes for why a technician cannot take a job.
MISSING_SKILL = "missing_skill"
AT_CAPACITY = "at_capacity"
NO_TIME = "no_feasible_time"


def haversine_matrix(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Great-circle distance (km) between every pair of points."""
    lat = np.radians(lats)[:, None]
    lon = np.radians(lons)[:, None]
    dlat = lat - lat.T
    dlon = lon - lon.T
    a = np.sin(dlat / 2) ** 2 + np.cos(lat) * np.cos(lat.T) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


class Problem:
    """A scenario plus precomputed distances and lookup tables."""

    def __init__(self, scenario: Scenario, weights: Weights | None = None):
        self.scenario = scenario
        self.weights = weights or Weights()
        self.techs: dict[str, Technician] = {t.id: t for t in scenario.technicians}
        self.jobs: dict[str, Job] = {j.id: j for j in scenario.jobs}

        # Node index: technicians' homes first, then job sites.
        self.node: dict[str, int] = {}
        lats, lons = [], []
        for t in scenario.technicians:
            self.node[f"home:{t.id}"] = len(lats)
            lats.append(t.home.lat)
            lons.append(t.home.lon)
        for j in scenario.jobs:
            self.node[j.id] = len(lats)
            lats.append(j.location.lat)
            lons.append(j.location.lon)

        straight = haversine_matrix(np.array(lats), np.array(lons)) if lats else np.zeros((0, 0))
        self.km = straight * scenario.road_factor
        self.minutes = np.ceil(self.km / scenario.speed_kmh * 60).astype(int)

    def dist(self, a: str, b: str) -> float:
        return float(self.km[self.node[a], self.node[b]])

    def travel_min(self, a: str, b: str) -> int:
        return int(self.minutes[self.node[a], self.node[b]])

    def has_skills(self, tech: Technician, job: Job) -> bool:
        return set(job.required_skills) <= set(tech.skills)

    def overqualification(self, tech: Technician, job: Job) -> int:
        return len(set(tech.skills) - set(job.required_skills))


@dataclass(slots=True)
class StopT:
    """Lightweight stop record used in the hot loop (converted for the API later)."""

    job_id: str
    arrival: int
    start: int
    end: int
    travel_km: float
    wait: int


@dataclass
class Schedule:
    stops: list[StopT]
    return_km: float
    cost: float


@dataclass
class RouteState:
    """A technician's ordered list of jobs, mutated as algorithms assign work."""

    tech: Technician
    job_ids: list[str] = field(default_factory=list)
    schedule: Schedule | None = None

    def __post_init__(self):
        if self.schedule is None:
            self.schedule = Schedule(stops=[], return_km=0.0, cost=0.0)


def simulate(problem: Problem, tech: Technician, job_ids: list[str]) -> Schedule | None:
    """Compute timings for a route; return None if any hard constraint fails."""
    if len(job_ids) > tech.max_jobs:
        return None
    w = problem.weights
    here = f"home:{tech.id}"
    t = tech.shift_start
    stops: list[StopT] = []
    cost = 0.0
    for jid in job_ids:
        job = problem.jobs[jid]
        km = problem.dist(here, jid)
        arrival = t + problem.travel_min(here, jid)
        start = max(arrival, job.window_start)
        if start > job.window_end:
            return None
        end = start + job.duration
        wait = start - arrival
        stops.append(StopT(jid, arrival, start, end, round(km, 2), wait))
        cost += w.travel_km * km + w.idle_minute * wait + w.overqualified_skill * problem.overqualification(tech, job)
        t, here = end, jid
    home = f"home:{tech.id}"
    return_km = problem.dist(here, home) if job_ids else 0.0
    if job_ids and t + problem.travel_min(here, home) > tech.shift_end:
        return None
    cost += w.travel_km * return_km
    return Schedule(stops=stops, return_km=round(return_km, 2), cost=cost)


@dataclass
class Insertion:
    tech_id: str
    position: int
    marginal_cost: float
    schedule: Schedule


def best_insertion(problem: Problem, route: RouteState, job: Job) -> Insertion | str:
    """Cheapest feasible position for `job` in `route`, or a reason code."""
    tech = route.tech
    if not problem.has_skills(tech, job):
        return MISSING_SKILL
    if len(route.job_ids) >= tech.max_jobs:
        return AT_CAPACITY
    best: Insertion | None = None
    for pos in range(len(route.job_ids) + 1):
        candidate = route.job_ids[:pos] + [job.id] + route.job_ids[pos:]
        sched = simulate(problem, tech, candidate)
        if sched is None:
            continue
        marginal = sched.cost - route.schedule.cost
        if best is None or marginal < best.marginal_cost:
            best = Insertion(tech.id, pos, marginal, sched)
    return best if best is not None else NO_TIME


def apply_insertion(route: RouteState, ins: Insertion, job_id: str) -> None:
    route.job_ids.insert(ins.position, job_id)
    route.schedule = ins.schedule


def new_routes(problem: Problem) -> dict[str, RouteState]:
    return {t.id: RouteState(tech=t) for t in problem.scenario.technicians}


def validate(problem: Problem, routes: dict[str, RouteState]) -> list[str]:
    """Independently re-check every hard constraint. Returns violations."""
    errors: list[str] = []
    seen: set[str] = set()
    for tid, route in routes.items():
        tech = problem.techs[tid]
        for jid in route.job_ids:
            if jid in seen:
                errors.append(f"{jid} assigned twice")
            seen.add(jid)
            if not problem.has_skills(tech, problem.jobs[jid]):
                errors.append(f"{tid} lacks skills for {jid}")
        if len(route.job_ids) > tech.max_jobs:
            errors.append(f"{tid} exceeds max_jobs")
        if route.job_ids and simulate(problem, tech, route.job_ids) is None:
            errors.append(f"{tid} route breaks a time window or shift")
    return errors


def fmt_time(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def safe_round(x: float, n: int = 2) -> float:
    return 0.0 if (x is None or math.isnan(x)) else round(x, n)
