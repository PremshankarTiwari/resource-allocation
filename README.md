# Resource Allocation Engine: field-service dispatch

Assigns field technicians to a day of maintenance and repair jobs at industrial
sites (wind farms, substations, plants), using three allocation strategies, and
compares them side by side on synchronized maps.

- **Backend:** Python, FastAPI, NumPy, SciPy
- **Frontend:** React, TypeScript, Vite, Leaflet with OpenStreetMap
- No paid services, no API keys

## Quick start

You need Python 3.10+ and Node.js 18+.

**1. Backend** (terminal 1)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs are then at http://localhost:8000/docs.

**2. Frontend** (terminal 2)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The dev server forwards `/api` requests to the
backend on port 8000.

**3. Tests and benchmark**

```bash
cd backend
pytest                        # 54 tests
python benchmark.py --seeds 20   # prints the comparison table used in ANALYSIS.md
```

Everything runs locally. The only network use is loading free OpenStreetMap
tiles and the IBM Plex web font in the browser; without internet the app still
works, with a blank map background and a system font.

## Using the app

- **Generate scenario:** pick a seed, team size, number of jobs and how many jobs
  each technician can do in a day. The same seed always gives the same scenario.
- **Compare plans:** each enabled algorithm gets its own map, metric strip and
  table column. Pan or zoom any map and the others follow, so differences line up.
- **Where the plans differ:** lists jobs that the algorithms handled
  differently, with coverage differences first. Select one (or click a job on any
  map) to see who each algorithm chose and why.
- **Place job on map:** add a job with a chosen priority and skill by clicking a
  map; all plans re-run immediately.
- **Cost weights:** change how much driving, waiting and over-qualification cost,
  and how much each priority is worth. Plans re-run as you type.

Setting "Jobs per technician" to 1 turns the problem into a pure assignment
problem, where Hungarian is provably optimal. That is a good way to see the
greedy-versus-batch difference.

## Approach

### Domain and data model (`backend/app/models.py`)

| Entity | Key fields |
|---|---|
| `Technician` (resource) | home location, skills, shift start/end, max jobs per day |
| `Job` (request) | site location, required skills, time window for starting work, duration, priority (normal, high, critical) |
| `Assignment` | job, technician, order in the route, arrival/start/end time, km driven |
| `Weights` | soft-constraint costs and the value of serving each priority |

Times are minutes after midnight to keep arithmetic simple. The generator
(`generator.py`) clusters jobs around named sites and puts technicians at
depots, because real maintenance work is clustered, and clustering is where
allocation strategies diverge.

### Constraints (`backend/app/core.py`)

| Type | Constraint |
|---|---|
| Hard | Technician has every required skill |
| Hard | Work starts no later than the job's window closes (arriving early means waiting) |
| Hard | Technician leaves home after shift start and is back home by shift end |
| Hard | At most `max_jobs` jobs per technician |
| Soft | Kilometres driven |
| Soft | Minutes spent waiting for a window to open |
| Soft | Over-qualification: each specialist skill a job doesn't need, to keep specialists free |
| Soft | Reward lost for each unserved job, by priority |

Technicians do several jobs a day, so assignment is really route building.
All algorithms use the same **cheapest insertion** step: try the new job at every
position in a technician's route, re-check every hard constraint, and price the
change in route cost. After solving, `validate()` independently re-checks every
route, and the API refuses to return a plan that breaks a hard constraint.

### Algorithms (`backend/app/algorithms/`)

| Algorithm | How it decides |
|---|---|
| **Greedy** | Sorts jobs by priority, then earliest window close, and gives each to the technician who can take it most cheaply right now. Decisions are final. |
| **Hungarian (batch rounds)** | Builds a job-by-technician cost matrix (insertion cost minus the job's priority reward) and solves it with SciPy's `linear_sum_assignment`. Each round gives every technician at most one more job, then re-prices what is left. Optimal within a round. |
| **Regret insertion** (custom heuristic) | Repeatedly assigns the job that would lose most by waiting: the largest gap between its best and second-best technician, or any job only one technician can still do. Priority levels are handled first. |

### Explanations

Every job gets a plain-language explanation from each algorithm: who was chosen,
arrival and start time, the next-best technician and the cost difference, why
other technicians were not considered (missing skill, at capacity, no slot that
fits), and an algorithm-specific note, such as the Hungarian round in which a
job was matched, or why Regret picked it when it did. Unassigned jobs explain
what blocked them.

### Metrics

Coverage, critical coverage, priority-weighted coverage, total and per-job
driving, average wait, utilization, workload spread across technicians, total
objective (the number every algorithm minimizes) and runtime. All metrics come
from one shared function so the comparison is fair.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness check |
| GET | `/api/algorithms` | Available algorithms |
| GET | `/api/scenario?seed=7&technicians=12&jobs=48&max_jobs=5` | Generate a scenario |
| POST | `/api/solve` | Body: `{scenario, algorithms, weights}`; returns one solution per algorithm |

The API is stateless: the client sends the scenario with each request, so the
UI can edit it freely without server-side storage.

## Project structure

```
backend/
  app/
    models.py          data model and validation
    core.py            distances, route simulation, constraints, insertion
    algorithms/        greedy.py, hungarian.py, regret.py, base.py (explanations)
    solver.py          runs an algorithm, validates, computes metrics
    generator.py       seeded scenario generator
    main.py            FastAPI app
  tests/               constraint, optimality, comparison and API tests
  benchmark.py         multi-seed comparison report
frontend/
  src/
    App.tsx            controls, layout, re-planning
    components/        MapPanel (synced maps), MetricsTable, JobInspector
ANALYSIS.md            algorithm comparison write-up
```

## What the tests cover

- Each hard constraint in isolation (skills, window, shift, capacity, waiting)
- Every algorithm respects all hard constraints across 8 random scenarios
- Every job is either assigned once or explained as unassigned
- Results are deterministic
- Hungarian matches a brute-force optimum when each technician takes one job
- Hand-built cases where Greedy is myopic and Hungarian fixes it, and where
  Regret protects a scarce specialist that Greedy wastes
- Critical jobs win when capacity is short; weights change decisions
- API validation: unknown algorithms, duplicate IDs, invalid time windows

See [ANALYSIS.md](ANALYSIS.md) for results and what they mean.
