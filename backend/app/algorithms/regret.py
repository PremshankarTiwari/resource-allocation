"""Regret insertion: a custom heuristic from vehicle-routing practice.

Insight: the job to assign next is the one that would lose the most if we
waited. "Regret" is the gap between a job's best and second-best technician.
A job with only one feasible technician, or a big gap, is assigned first;
jobs that many technicians can do cheaply can wait.

Priority still comes first: all critical jobs are considered before high,
and high before normal. Within a priority level, highest regret goes first.

Implementation detail: after each assignment only one route changes, so only
that technician's column of insertion costs is recomputed (cached otherwise).
"""
from __future__ import annotations

import math

from ..core import Insertion, Problem, apply_insertion, best_insertion, new_routes
from .base import AllocationResult, Allocator, explain_assignment, explain_unassigned, split_options


class RegretAllocator(Allocator):
    key = "regret"
    name = "Regret insertion"
    description = "Assigns the job that would lose most by waiting first: the biggest gap between its best and next-best technician."

    def solve(self, problem: Problem) -> AllocationResult:
        routes = new_routes(problem)
        result = AllocationResult(routes=routes)
        pending = {j.id: j for j in problem.scenario.jobs}
        options = {jid: {tid: best_insertion(problem, r, job) for tid, r in routes.items()} for jid, job in pending.items()}
        step = 0

        while pending:
            best_key, best_jid = None, None
            for jid, job in pending.items():
                feasible, _ = split_options(options[jid])
                if not feasible:
                    continue
                if len(feasible) == 1:
                    regret = math.inf
                else:
                    regret = feasible[1].marginal_cost - feasible[0].marginal_cost
                key = (int(job.priority), regret, -job.window_end, jid)
                if best_key is None or key > best_key:
                    best_key, best_jid = key, jid

            if best_jid is None:
                # Nothing left is feasible; routes only fill up, so it never will be.
                for jid, job in pending.items():
                    _, reasons = split_options(options[jid])
                    result.explanations[jid] = explain_unassigned(job, reasons)
                break

            step += 1
            job = pending.pop(best_jid)
            feasible, reasons = split_options(options[best_jid])
            chosen: Insertion = feasible[0]
            apply_insertion(routes[chosen.tech_id], chosen, job.id)
            regret = best_key[1]
            if math.isinf(regret):
                note = f"Picked at step {step} because only one technician could still take it."
            else:
                note = f"Picked at step {step}: waiting would have cost {regret:.1f} (best vs. next-best gap)."
            result.explanations[job.id] = explain_assignment(problem, job, chosen, feasible, reasons, note)

            changed = routes[chosen.tech_id]
            for jid, other in pending.items():
                options[jid][changed.tech.id] = best_insertion(problem, changed, other)
            del options[best_jid]
        return result
