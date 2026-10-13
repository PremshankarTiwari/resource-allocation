import itertools

import numpy as np
import pytest

from app.algorithms import ALLOCATORS
from app.core import Problem, best_insertion, haversine_matrix, new_routes, simulate
from app.generator import generate
from app.models import Job, Location, Priority, Scenario, Technician, Weights
from app.solver import solve

ALGOS = list(ALLOCATORS)


# ---------- helpers ----------

def tech(id, lon, skills=("electrical",), shift=(480, 1020), max_jobs=1):
    return Technician(id=id, name=id, home=Location(lat=30.0, lon=lon), skills=list(skills),
                      shift_start=shift[0], shift_end=shift[1], max_jobs=max_jobs)


def job(id, lon, skills=("electrical",), window=(480, 1000), duration=30, priority=Priority.NORMAL):
    return Job(id=id, site="Test site", location=Location(lat=30.0, lon=lon), required_skills=list(skills),
               window_start=window[0], window_end=window[1], duration=duration, priority=priority)


# ---------- geometry ----------

def test_haversine_known_distance():
    # Austin to Dallas is roughly 293 km in a straight line.
    d = haversine_matrix(np.array([30.2672, 32.7767]), np.array([-97.7431, -96.7970]))
    assert d[0, 1] == pytest.approx(293, abs=5)
    assert d[0, 0] == 0
    assert d[0, 1] == pytest.approx(d[1, 0])


# ---------- hard constraints ----------

def test_skill_mismatch_is_rejected():
    sc = Scenario(technicians=[tech("A", 0)], jobs=[job("J1", 0.01, skills=("high_voltage",))])
    p = Problem(sc)
    assert best_insertion(p, new_routes(p)["A"], p.jobs["J1"]) == "missing_skill"


def test_time_window_is_enforced():
    # The site is ~130 km away (2.5 h+ drive) but the window closes 30 min after the shift starts.
    sc = Scenario(technicians=[tech("A", 0)], jobs=[job("J1", 1.0, window=(480, 510))])
    p = Problem(sc)
    assert simulate(p, p.techs["A"], ["J1"]) is None


def test_technician_must_get_home_before_shift_ends():
    sc = Scenario(technicians=[tech("A", 0, shift=(480, 600))], jobs=[job("J1", 0.3, window=(480, 600), duration=60)])
    p = Problem(sc)
    assert simulate(p, p.techs["A"], ["J1"]) is None


def test_capacity_is_enforced():
    sc = Scenario(technicians=[tech("A", 0, max_jobs=1)], jobs=[job("J1", 0.01), job("J2", 0.02)])
    p = Problem(sc)
    routes = new_routes(p)
    routes["A"].job_ids = ["J1"]
    assert best_insertion(p, routes["A"], p.jobs["J2"]) == "at_capacity"


def test_waiting_for_window_is_allowed_and_recorded():
    sc = Scenario(technicians=[tech("A", 0)], jobs=[job("J1", 0.01, window=(600, 700))])
    p = Problem(sc)
    sched = simulate(p, p.techs["A"], ["J1"])
    assert sched is not None
    assert sched.stops[0].start == 600
    assert sched.stops[0].wait > 0


@pytest.mark.parametrize("algorithm", ALGOS)
@pytest.mark.parametrize("seed", range(8))
def test_every_algorithm_respects_hard_constraints(algorithm, seed):
    # solve() re-validates every route independently and raises on any violation.
    sc = generate(seed=seed, technicians=10, jobs=45)
    sol = solve(sc, algorithm)
    p = Problem(sc)
    for a in sol.assignments:
        assert p.has_skills(p.techs[a.technician_id], p.jobs[a.job_id])
        j = p.jobs[a.job_id]
        assert a.start <= j.window_end


@pytest.mark.parametrize("algorithm", ALGOS)
def test_every_job_is_assigned_or_explained_exactly_once(algorithm):
    sc = generate(seed=3, technicians=8, jobs=40)
    sol = solve(sc, algorithm)
    assigned = [a.job_id for a in sol.assignments]
    assert len(assigned) == len(set(assigned))
    assert set(assigned) | set(sol.unassigned) == {j.id for j in sc.jobs}
    assert not set(assigned) & set(sol.unassigned)
    assert {e.job_id for e in sol.explanations} == {j.id for j in sc.jobs}
    for e in sol.explanations:
        assert e.summary


@pytest.mark.parametrize("algorithm", ALGOS)
def test_results_are_deterministic(algorithm):
    sc = generate(seed=11, technicians=8, jobs=30)
    a, b = solve(sc, algorithm), solve(sc, algorithm)
    assert [x.model_dump() for x in a.assignments] == [x.model_dump() for x in b.assignments]


# ---------- algorithm quality ----------

def _brute_force_best_objective(sc: Scenario) -> float:
    """Exact optimum for one-job-per-technician problems by trying every matching."""
    p = Problem(sc)
    techs, jobs = sc.technicians, sc.jobs
    best = float("inf")
    slots = [None] + [j.id for j in jobs]
    for combo in itertools.product(slots, repeat=len(techs)):
        chosen = [c for c in combo if c]
        if len(chosen) != len(set(chosen)):
            continue
        total = 0.0
        ok = True
        for t, jid in zip(techs, combo):
            if jid is None:
                continue
            if not p.has_skills(t, p.jobs[jid]):
                ok = False
                break
            s = simulate(p, t, [jid])
            if s is None:
                ok = False
                break
            total += s.cost
        if ok:
            total += sum(p.weights.reward(j.priority) for j in jobs if j.id not in chosen)
            best = min(best, total)
    return best


@pytest.mark.parametrize("seed", range(6))
def test_hungarian_is_optimal_when_each_technician_takes_one_job(seed):
    rng = np.random.default_rng(seed)
    techs = [tech(f"T{i}", float(rng.uniform(0, 0.3)), skills=("electrical", "mechanical")) for i in range(4)]
    jobs = [
        job(f"J{i}", float(rng.uniform(0, 0.3)), skills=(str(rng.choice(["electrical", "mechanical"])),),
            priority=Priority(int(rng.integers(1, 4))))
        for i in range(4)
    ]
    sc = Scenario(technicians=techs, jobs=jobs)
    hungarian = solve(sc, "hungarian").metrics.objective
    assert hungarian == pytest.approx(_brute_force_best_objective(sc), abs=0.2)
    assert hungarian <= solve(sc, "greedy").metrics.objective + 1e-6


def test_greedy_is_myopic_and_hungarian_fixes_it():
    # A is close to both jobs; B is close only to J1. Greedy handles J1 first
    # (earlier window close), gives it to A, and must send B far away for J2.
    # The batch matching sends A to J2 and B to J1 for less total driving.
    sc = Scenario(
        technicians=[tech("A", 0.00), tech("B", 0.10)],
        jobs=[job("J1", 0.05, window=(480, 900)), job("J2", -0.05, window=(480, 1000))],
    )
    greedy, hungarian = solve(sc, "greedy"), solve(sc, "hungarian")
    assert greedy.metrics.jobs_assigned == hungarian.metrics.jobs_assigned == 2
    assert hungarian.metrics.total_travel_km < greedy.metrics.total_travel_km
    g = {a.job_id: a.technician_id for a in greedy.assignments}
    h = {a.job_id: a.technician_id for a in hungarian.assignments}
    assert g == {"J1": "A", "J2": "B"}
    assert h == {"J1": "B", "J2": "A"}


def test_regret_protects_the_scarce_specialist():
    # Only S can do the high-voltage job. Greedy takes the routine job first and
    # gives it to S (closest), so the high-voltage job goes unserved.
    # Regret sees that the high-voltage job has a single option and assigns it first.
    sc = Scenario(
        technicians=[tech("S", 0.00, skills=("electrical", "high_voltage")), tech("G", 0.08, skills=("electrical",))],
        jobs=[
            job("ROUTINE", 0.01, skills=("electrical",), window=(480, 700)),
            job("HV", 0.02, skills=("high_voltage",), window=(480, 1000)),
        ],
    )
    greedy, regret = solve(sc, "greedy"), solve(sc, "regret")
    assert "HV" in greedy.unassigned
    assert regret.unassigned == []
    hv = next(e for e in regret.explanations if e.job_id == "HV")
    assert "only one technician" in hv.summary


def test_critical_jobs_win_when_capacity_is_short():
    # One technician, two jobs that both fit only in the same time slot.
    sc = Scenario(
        technicians=[tech("A", 0)],
        jobs=[
            job("NORMAL", 0.01, window=(480, 500), priority=Priority.NORMAL),
            job("CRITICAL", 0.02, window=(480, 500), priority=Priority.CRITICAL),
        ],
    )
    for algorithm in ALGOS:
        sol = solve(sc, algorithm)
        assert [a.job_id for a in sol.assignments] == ["CRITICAL"], algorithm
        assert sol.metrics.critical_coverage_pct == 100


def test_unassigned_explanation_names_the_reason():
    sc = Scenario(technicians=[tech("A", 0)], jobs=[job("J1", 0.01, skills=("hydraulics",))])
    sol = solve(sc, "greedy")
    assert sol.unassigned == ["J1"]
    assert "missing a required skill" in sol.explanations[0].summary


def test_weights_change_decisions():
    # With a heavy over-qualification penalty, the generalist gets the routine job
    # even though the specialist is slightly closer.
    sc = Scenario(
        technicians=[tech("SPEC", 0.000, skills=("electrical", "high_voltage", "controls")), tech("GEN", 0.002)],
        jobs=[job("J1", 0.001)],
    )
    cheap = solve(sc, "greedy", Weights(overqualified_skill=0, travel_km=1))
    strict = solve(sc, "greedy", Weights(overqualified_skill=50, travel_km=1))
    assert strict.assignments[0].technician_id == "GEN"
    assert cheap.metrics.total_travel_km <= strict.metrics.total_travel_km + 1e-9
