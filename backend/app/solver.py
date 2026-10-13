"""Runs an allocator and turns its routes into a scored, explained Solution."""
from __future__ import annotations

import statistics
import time

from .algorithms import ALLOCATORS
from .core import Problem, RouteState, validate
from .models import Assignment, Metrics, Priority, Route, Scenario, Solution, Stop, Weights


def compute_metrics(problem: Problem, routes: dict[str, RouteState], runtime_ms: float) -> Metrics:
    jobs = problem.scenario.jobs
    w = problem.weights
    assigned = {jid for r in routes.values() for jid in r.job_ids}

    critical = [j for j in jobs if j.priority == Priority.CRITICAL]
    reward_total = sum(w.reward(j.priority) for j in jobs)
    reward_served = sum(w.reward(j.priority) for j in jobs if j.id in assigned)

    travel_km = sum(s.travel_km for r in routes.values() for s in r.schedule.stops) + sum(
        r.schedule.return_km for r in routes.values()
    )
    waits = [s.wait for r in routes.values() for s in r.schedule.stops]

    # Busy time = on-site work + driving. Waiting for a window is not counted.
    work_min = sum(problem.jobs[s.job_id].duration for r in routes.values() for s in r.schedule.stops)
    busy = work_min + travel_km / problem.scenario.speed_kmh * 60
    shift_total = sum(t.shift_end - t.shift_start for t in problem.scenario.technicians)

    route_cost = sum(r.schedule.cost for r in routes.values())
    unserved_penalty = sum(w.reward(j.priority) for j in jobs if j.id not in assigned)
    loads = [len(r.job_ids) for r in routes.values()]

    def pct(a: float, b: float) -> float:
        return round(100 * a / b, 1) if b else 100.0

    return Metrics(
        jobs_total=len(jobs),
        jobs_assigned=len(assigned),
        coverage_pct=pct(len(assigned), len(jobs)),
        critical_coverage_pct=pct(sum(1 for j in critical if j.id in assigned), len(critical)),
        priority_weighted_coverage_pct=pct(reward_served, reward_total),
        total_travel_km=round(travel_km, 1),
        travel_km_per_job=round(travel_km / len(assigned), 2) if assigned else 0.0,
        avg_wait_min=round(statistics.fmean(waits), 1) if waits else 0.0,
        utilization_pct=pct(busy, shift_total),
        workload_std=round(statistics.pstdev(loads), 2) if loads else 0.0,
        objective=round(route_cost + unserved_penalty, 1),
        runtime_ms=round(runtime_ms, 1),
    )


def solve(scenario: Scenario, algorithm: str, weights: Weights | None = None) -> Solution:
    if algorithm not in ALLOCATORS:
        raise KeyError(f"Unknown algorithm '{algorithm}'. Options: {', '.join(ALLOCATORS)}")
    problem = Problem(scenario, weights)
    allocator = ALLOCATORS[algorithm]

    started = time.perf_counter()
    result = allocator.solve(problem)
    runtime_ms = (time.perf_counter() - started) * 1000

    errors = validate(problem, result.routes)
    if errors:  # A bug, never expected: fail loudly rather than show a bad plan.
        raise RuntimeError(f"{algorithm} broke hard constraints: {errors[:5]}")

    assignments, routes = [], []
    for tid, r in result.routes.items():
        stops = [
            Stop(job_id=s.job_id, arrival=s.arrival, start=s.start, end=s.end, travel_km=s.travel_km, wait=s.wait)
            for s in r.schedule.stops
        ]
        routes.append(Route(technician_id=tid, stops=stops, return_km=r.schedule.return_km))
        for seq, s in enumerate(stops, start=1):
            assignments.append(
                Assignment(
                    job_id=s.job_id, technician_id=tid, sequence=seq,
                    arrival=s.arrival, start=s.start, end=s.end, travel_km=s.travel_km,
                )
            )

    assigned = {a.job_id for a in assignments}
    return Solution(
        algorithm=algorithm,
        assignments=assignments,
        routes=routes,
        unassigned=[j.id for j in scenario.jobs if j.id not in assigned],
        explanations=[result.explanations[j.id] for j in scenario.jobs if j.id in result.explanations],
        metrics=compute_metrics(problem, result.routes, runtime_ms),
    )
