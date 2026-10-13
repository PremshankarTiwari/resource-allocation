from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass, field

from ..core import AT_CAPACITY, MISSING_SKILL, NO_TIME, Insertion, Problem, RouteState, fmt_time
from ..models import Explanation, Job

REASON_TEXT = {
    MISSING_SKILL: "missing a required skill",
    AT_CAPACITY: "already at their daily job limit",
    NO_TIME: "with no free slot that fits its window and their shift",
}


@dataclass
class AllocationResult:
    routes: dict[str, RouteState]
    explanations: dict[str, Explanation] = field(default_factory=dict)


class Allocator(ABC):
    key: str
    name: str
    description: str

    @abstractmethod
    def solve(self, problem: Problem) -> AllocationResult: ...


def split_options(options: dict[str, Insertion | str]) -> tuple[list[Insertion], Counter]:
    """Separate feasible insertions (sorted by cost) from rejection reasons."""
    feasible = sorted((o for o in options.values() if isinstance(o, Insertion)), key=lambda i: i.marginal_cost)
    reasons = Counter(o for o in options.values() if isinstance(o, str))
    return feasible, reasons


def describe_rejections(reasons: Counter) -> str:
    parts = [f"{n} {'technician' if n == 1 else 'technicians'} {REASON_TEXT[r]}" for r, n in reasons.most_common()]
    return "; ".join(parts)


def explain_assignment(
    problem: Problem,
    job: Job,
    chosen: Insertion,
    feasible: list[Insertion],
    reasons: Counter,
    note: str = "",
) -> Explanation:
    tech = problem.techs[chosen.tech_id]
    stop = next(s for s in chosen.schedule.stops if s.job_id == job.id)
    others = [i for i in feasible if i.tech_id != chosen.tech_id]
    runner = others[0] if others else None

    summary = (
        f"{tech.name} arrives {fmt_time(stop.arrival)}, starts {fmt_time(stop.start)} "
        f"(window {fmt_time(job.window_start)}-{fmt_time(job.window_end)}), "
        f"driving {stop.travel_km:.1f} km to the site."
    )
    if runner:
        delta = runner.marginal_cost - chosen.marginal_cost
        rname = problem.techs[runner.tech_id].name
        if delta >= 0:
            summary += f" Next best was {rname}, costing {delta:.1f} more."
        else:
            summary += f" {rname} was {-delta:.1f} cheaper for this job alone."
    else:
        summary += " No other technician could take it."
    if note:
        summary += f" {note}"
    if reasons:
        summary += f" Not considered: {describe_rejections(reasons)}."

    return Explanation(
        job_id=job.id,
        assigned_to=chosen.tech_id,
        summary=summary,
        cost=round(chosen.marginal_cost, 2),
        runner_up=runner.tech_id if runner else None,
        runner_up_cost=round(runner.marginal_cost, 2) if runner else None,
        rejected=dict(reasons),
    )


def explain_unassigned(job: Job, reasons: Counter, note: str = "") -> Explanation:
    summary = f"Left unassigned: {describe_rejections(reasons)}." if reasons else "Left unassigned."
    if note:
        summary += f" {note}"
    return Explanation(job_id=job.id, assigned_to=None, summary=summary, rejected=dict(reasons))
