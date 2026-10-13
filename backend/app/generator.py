"""Seeded, realistic-looking scenarios for a field-service team.

Jobs cluster around industrial sites (wind farms, substations, plants) instead
of being scattered uniformly, because real maintenance work is clustered and
clustering is exactly where batch and greedy decisions start to differ.
Technicians start from a few depots. Same seed -> same scenario.
"""
from __future__ import annotations

import math
import random

from .models import Job, Location, Priority, Scenario, Technician

CENTER = (30.27, -97.74)  # Central Texas: plenty of wind farms and substations.

SITES = [
    ("Mesa Ridge Wind Farm", 0.55, -0.45),
    ("Pecan Creek Substation", 0.20, 0.35),
    ("Blackland Solar Plant", -0.35, 0.50),
    ("Lampasas Wind Farm", 0.65, 0.25),
    ("San Marcos Pump Station", -0.45, -0.20),
    ("Llano Water Treatment", 0.10, -0.70),
    ("Bastrop Gas Turbine Plant", -0.10, 0.80),
    ("Georgetown Substation", 0.45, 0.05),
]

DEPOTS = [("North depot", 0.30, -0.05), ("South depot", -0.30, 0.10), ("East depot", 0.05, 0.40)]

# Common skills first; high_voltage is the scarce specialism.
SKILLS = ["mechanical", "electrical", "hydraulics", "controls", "high_voltage"]
SKILL_WEIGHTS = [0.32, 0.30, 0.16, 0.14, 0.08]

FIRST_NAMES = [
    "Ana", "Ben", "Chen", "Dev", "Eli", "Farah", "Gus", "Hana", "Ivan", "Jade", "Kofi", "Lena",
    "Mo", "Nia", "Omar", "Priya", "Quinn", "Raj", "Sara", "Tomas", "Uma", "Vik", "Wren", "Yusuf",
]

SHIFTS = [(420, 900), (480, 960), (540, 1020), (600, 1080)]  # 07-15, 08-16, 09-17, 10-18


def _jitter(rng: random.Random, lat: float, lon: float, km: float) -> Location:
    r = km * math.sqrt(rng.random())
    theta = rng.random() * 2 * math.pi
    dlat = (r * math.cos(theta)) / 111.0
    dlon = (r * math.sin(theta)) / (111.0 * math.cos(math.radians(lat)))
    return Location(lat=round(lat + dlat, 5), lon=round(lon + dlon, 5))


SPREAD = 0.45  # Scales the layout: roughly a 90 km wide service region.


def _offset(dlat: float, dlon: float) -> tuple[float, float]:
    return CENTER[0] + dlat * SPREAD, CENTER[1] + dlon * SPREAD


def _pick_skills(rng: random.Random, k: int) -> list[str]:
    chosen: list[str] = []
    while len(chosen) < k:
        s = rng.choices(SKILLS, weights=SKILL_WEIGHTS)[0]
        if s not in chosen:
            chosen.append(s)
    return sorted(chosen)


def generate(seed: int = 7, technicians: int = 12, jobs: int = 48, max_jobs: int = 5) -> Scenario:
    rng = random.Random(seed)

    techs: list[Technician] = []
    for i in range(technicians):
        _, dlat, dlon = DEPOTS[i % len(DEPOTS)]
        home = _jitter(rng, *_offset(dlat, dlon), km=6)
        skills = _pick_skills(rng, rng.choice([2, 2, 3, 3, 4]))
        start, end = rng.choice(SHIFTS)
        name = FIRST_NAMES[i % len(FIRST_NAMES)] + ("" if i < len(FIRST_NAMES) else f" {i // len(FIRST_NAMES) + 1}")
        techs.append(
            Technician(id=f"T{i + 1:02d}", name=name, home=home, skills=skills,
                       shift_start=start, shift_end=end, max_jobs=max_jobs)
        )

    out_jobs: list[Job] = []
    for i in range(jobs):
        site, dlat, dlon = rng.choice(SITES)
        loc = _jitter(rng, *_offset(dlat, dlon), km=4)
        required = _pick_skills(rng, rng.choice([1, 1, 1, 2]))
        window_start = rng.randrange(420, 840 + 1, 30)
        window_end = min(window_start + rng.choice([60, 120, 180, 240]), 1020)
        priority = rng.choices([Priority.NORMAL, Priority.HIGH, Priority.CRITICAL], weights=[0.55, 0.30, 0.15])[0]
        out_jobs.append(
            Job(
                id=f"J{i + 1:03d}", site=site, location=loc, required_skills=required,
                window_start=window_start, window_end=window_end,
                duration=rng.choice([30, 45, 60, 90, 120]), priority=priority,
            )
        )
    return Scenario(technicians=techs, jobs=out_jobs)
