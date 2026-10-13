"""HTTP API. Stateless: the client sends the scenario with every solve request,
so the UI can add jobs or technicians and re-run without server-side storage."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .algorithms import ALLOCATORS
from .generator import generate
from .models import Scenario, Solution, Weights
from .solver import solve

app = FastAPI(title="Resource Allocation Engine", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AlgorithmInfo(BaseModel):
    key: str
    name: str
    description: str


class SolveRequest(BaseModel):
    scenario: Scenario
    algorithms: list[str] = Field(default_factory=lambda: list(ALLOCATORS))
    weights: Weights = Field(default_factory=Weights)


class SolveResponse(BaseModel):
    solutions: dict[str, Solution]


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/algorithms", response_model=list[AlgorithmInfo])
def algorithms() -> list[AlgorithmInfo]:
    return [AlgorithmInfo(key=a.key, name=a.name, description=a.description) for a in ALLOCATORS.values()]


@app.get("/api/scenario", response_model=Scenario)
def scenario(
    seed: int = Query(7, ge=0),
    technicians: int = Query(12, ge=1, le=60),
    jobs: int = Query(48, ge=1, le=300),
    max_jobs: int = Query(5, ge=1, le=12, description="Daily job limit per technician"),
) -> Scenario:
    return generate(seed=seed, technicians=technicians, jobs=jobs, max_jobs=max_jobs)


@app.post("/api/solve", response_model=SolveResponse)
def solve_endpoint(req: SolveRequest) -> SolveResponse:
    unknown = [a for a in req.algorithms if a not in ALLOCATORS]
    if unknown:
        raise HTTPException(422, f"Unknown algorithm(s): {', '.join(unknown)}. Options: {', '.join(ALLOCATORS)}")
    ids = [j.id for j in req.scenario.jobs] + [t.id for t in req.scenario.technicians]
    if len(ids) != len(set(ids)):
        raise HTTPException(422, "Job and technician IDs must be unique.")
    return SolveResponse(solutions={a: solve(req.scenario, a, req.weights) for a in req.algorithms})
