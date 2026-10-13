"""Compare all algorithms across scenario shapes and many seeds.

Usage:  python benchmark.py            (prints a Markdown report)
        python benchmark.py --seeds 50
"""
from __future__ import annotations

import argparse
import statistics as st
from collections import Counter

from app.algorithms import ALLOCATORS
from app.generator import generate
from app.solver import solve

SHAPES = [
    ("One job each, supply = demand", 12, 12, 1),
    ("One job each, 2x more jobs than technicians", 12, 24, 1),
    ("Light day (multi-job routes)", 12, 30, 5),
    ("Busy day (multi-job routes)", 12, 48, 5),
    ("Overloaded day (multi-job routes)", 20, 120, 5),
]


def run(seeds: int) -> str:
    lines = [
        f"Averages over {seeds} seeds per row. Objective = route cost + reward lost on unserved jobs (lower is better). "
        "Wins = seeds where the algorithm had the lowest objective (ties count for all).",
        "",
        "| Scenario | Algorithm | Coverage % | Priority-weighted % | Critical % | Travel km | Objective | Wins | Runtime ms |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, techs, jobs, max_jobs in SHAPES:
        rows = {a: [] for a in ALLOCATORS}
        wins: Counter = Counter()
        for seed in range(seeds):
            scenario = generate(seed=seed, technicians=techs, jobs=jobs, max_jobs=max_jobs)
            metrics = {a: solve(scenario, a).metrics for a in ALLOCATORS}
            best = min(m.objective for m in metrics.values())
            for a, m in metrics.items():
                rows[a].append(m)
                if m.objective <= best + 1e-6:
                    wins[a] += 1
        for i, (a, ms) in enumerate(rows.items()):
            name = ALLOCATORS[a].name
            scen = f"{label} ({techs} techs, {jobs} jobs)" if i == 0 else ""
            lines.append(
                f"| {scen} | {name} | {st.mean(m.coverage_pct for m in ms):.1f} "
                f"| {st.mean(m.priority_weighted_coverage_pct for m in ms):.1f} "
                f"| {st.mean(m.critical_coverage_pct for m in ms):.1f} "
                f"| {st.mean(m.total_travel_km for m in ms):.0f} "
                f"| {st.mean(m.objective for m in ms):.0f} | {wins[a]} "
                f"| {st.mean(m.runtime_ms for m in ms):.1f} |"
            )
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=20)
    print(run(parser.parse_args().seeds))
