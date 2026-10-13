"""Hungarian (Kuhn-Munkres) in batch rounds.

The Hungarian algorithm finds the optimal one-to-one matching between jobs and
technicians for a cost matrix. Technicians can do several jobs a day, so we
solve it in rounds: each round gives every technician at most one more job,
choosing the set of pairs with the lowest total cost. Then routes are updated
and the next round re-prices the remaining jobs against the new routes.

Within a round the matching is globally optimal. Across rounds it is still
sequential, so it is not a full vehicle-routing optimum (which is NP-hard).

Cost of pairing job j with technician t:
    marginal route cost (travel, waiting, over-qualification) - reward(priority)
The reward makes serving urgent jobs worth more than any realistic travel
saving, so the matching prefers coverage of critical work first.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import linear_sum_assignment

from ..core import Insertion, Problem, apply_insertion, best_insertion, new_routes
from .base import AllocationResult, Allocator, explain_assignment, explain_unassigned, split_options

INFEASIBLE = 1e9


class HungarianAllocator(Allocator):
    key = "hungarian"
    name = "Hungarian (batch rounds)"
    description = "Each round finds the lowest-total-cost matching of jobs to technicians, one job per technician."

    def solve(self, problem: Problem) -> AllocationResult:
        routes = new_routes(problem)
        result = AllocationResult(routes=routes)
        pending = list(problem.scenario.jobs)
        tech_ids = list(routes)
        round_no = 0

        while pending:
            round_no += 1
            options = {
                job.id: {tid: best_insertion(problem, routes[tid], job) for tid in tech_ids} for job in pending
            }
            cost = np.full((len(pending), len(tech_ids)), INFEASIBLE)
            for r, job in enumerate(pending):
                reward = problem.weights.reward(job.priority)
                for c, tid in enumerate(tech_ids):
                    opt = options[job.id][tid]
                    if isinstance(opt, Insertion):
                        cost[r, c] = opt.marginal_cost - reward

            # A job with no feasible technician now can never become feasible
            # later: routes only get fuller. Record it and drop it.
            still_possible = []
            for r, job in enumerate(pending):
                if np.all(cost[r] >= INFEASIBLE):
                    _, reasons = split_options(options[job.id])
                    result.explanations[job.id] = explain_unassigned(job, reasons)
                else:
                    still_possible.append(r)
            if not still_possible:
                break
            cost = cost[still_possible]
            pending = [pending[r] for r in still_possible]

            rows, cols = linear_sum_assignment(cost)
            matched_by_tech = {tech_ids[c]: pending[r].id for r, c in zip(rows, cols) if cost[r, c] < INFEASIBLE}
            assigned_now = set()
            for r, c in zip(rows, cols):
                if cost[r, c] >= INFEASIBLE:
                    continue
                job, tid = pending[r], tech_ids[c]
                feasible, reasons = split_options(options[job.id])
                chosen = options[job.id][tid]
                note = f"Matched in batch round {round_no}."
                cheapest = feasible[0]
                if cheapest.tech_id != tid and cheapest.tech_id in matched_by_tech:
                    other = matched_by_tech[cheapest.tech_id]
                    note += (
                        f" The matching gave {problem.techs[cheapest.tech_id].name} job {other} instead,"
                        f" which lowered the round's total cost."
                    )
                apply_insertion(routes[tid], chosen, job.id)
                result.explanations[job.id] = explain_assignment(problem, job, chosen, feasible, reasons, note)
                assigned_now.add(job.id)
            pending = [j for j in pending if j.id not in assigned_now]
        return result
