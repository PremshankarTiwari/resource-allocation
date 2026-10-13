"""Greedy: take jobs one at a time, give each to the cheapest available technician.

Order: most urgent first (priority, then earliest window close). Each decision
is final and ignores how it affects jobs still waiting in the queue.
"""
from __future__ import annotations

from ..core import Problem, apply_insertion, best_insertion, new_routes
from .base import AllocationResult, Allocator, explain_assignment, explain_unassigned, split_options


class GreedyAllocator(Allocator):
    key = "greedy"
    name = "Greedy"
    description = "Jobs in priority order; each goes to the cheapest feasible technician right now."

    def solve(self, problem: Problem) -> AllocationResult:
        routes = new_routes(problem)
        result = AllocationResult(routes=routes)
        queue = sorted(
            problem.scenario.jobs,
            key=lambda j: (-int(j.priority), j.window_end, j.window_start, j.id),
        )
        for position, job in enumerate(queue, start=1):
            options = {tid: best_insertion(problem, r, job) for tid, r in routes.items()}
            feasible, reasons = split_options(options)
            if not feasible:
                result.explanations[job.id] = explain_unassigned(job, reasons)
                continue
            chosen = feasible[0]
            apply_insertion(routes[chosen.tech_id], chosen, job.id)
            result.explanations[job.id] = explain_assignment(
                problem, job, chosen, feasible, reasons, note=f"Decided {position} of {len(queue)} in the queue."
            )
        return result
