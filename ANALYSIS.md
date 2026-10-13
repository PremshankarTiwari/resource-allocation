# Algorithm comparison

## Setup

All three algorithms share the same feasibility rules and the same cost function
(`backend/app/core.py`), so differences come only from how they decide. Each
row below averages 20 generated scenarios (seeds 0 to 19). Reproduce with
`python benchmark.py --seeds 20` from `backend/`.

**Objective** (lower is better) = driving cost + waiting cost + over-qualification
cost + the reward lost on every job left unserved (critical 1000, high 400,
normal 150). The reward term makes covering urgent work dominate travel savings.

| Scenario | Algorithm | Coverage % | Priority-weighted % | Critical % | Travel km | Objective | Wins | Runtime ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| One job each, supply = demand (12 techs, 12 jobs) | Greedy | 87.5 | 91.6 | 92.5 | 590 | 1185 | 0 | 0.7 |
|  | Hungarian (batch rounds) | 95.8 | 95.6 | 92.5 | 632 | 1104 | 20 | 1.1 |
|  | Regret insertion | 92.9 | 94.5 | 92.5 | 649 | 1164 | 1 | 1.3 |
| One job each, 2x more jobs than technicians (12 techs, 24 jobs) | Greedy | 50.0 | 73.4 | 95.2 | 747 | 3231 | 0 | 1.0 |
|  | Hungarian (batch rounds) | 50.0 | 75.4 | 95.8 | 645 | 2959 | 20 | 2.2 |
|  | Regret insertion | 50.0 | 74.3 | 95.8 | 739 | 3162 | 0 | 3.1 |
| Light day, multi-job routes (12 techs, 30 jobs) | Greedy | 94.0 | 95.5 | 95.8 | 989 | 1709 | 5 | 4.2 |
|  | Hungarian (batch rounds) | 94.7 | 95.6 | 95.8 | 1090 | 1856 | 2 | 5.4 |
|  | Regret insertion | 95.8 | 96.3 | 95.8 | 1002 | 1622 | 13 | 11.0 |
| Busy day, multi-job routes (12 techs, 48 jobs) | Greedy | 85.6 | 91.8 | 97.2 | 1402 | 3058 | 2 | 7.5 |
|  | Hungarian (batch rounds) | 86.6 | 92.2 | 97.2 | 1335 | 2932 | 6 | 13.7 |
|  | Regret insertion | 88.9 | 93.5 | 97.2 | 1420 | 2791 | 12 | 23.6 |
| Overloaded day, multi-job routes (20 techs, 120 jobs) | Greedy | 71.7 | 86.6 | 98.7 | 2487 | 8493 | 1 | 23.5 |
|  | Hungarian (batch rounds) | 73.8 | 87.8 | 99.4 | 1990 | 7555 | 14 | 78.7 |
|  | Regret insertion | 72.0 | 87.3 | 99.4 | 2482 | 8192 | 5 | 114.3 |

"Wins" counts the seeds where an algorithm had the lowest objective; ties count
for every tied algorithm, so a row can sum to more than 20.

## What I learned

### 1. When each technician takes one job, Hungarian is optimal, and it shows

With one job per technician the problem is a pure assignment problem, which the
Hungarian algorithm solves exactly. A test checks this against brute force on
random small instances (`test_hungarian_is_optimal_when_each_technician_takes_one_job`).
It won all 20 seeds in both one-job scenarios.

The gap is largest when supply roughly equals demand: Hungarian covered 95.8%
of jobs against Greedy's 87.5%. Greedy commits each technician to the first job
that wants them, so a technician who was the only option for a later job may
already be taken. The smallest version of this is in
`test_greedy_is_myopic_and_hungarian_fixes_it`: Greedy sends the technician
who is close to both jobs to the first one, forcing the other technician on a
long drive. The batch matching swaps them and drives less in total.

When jobs outnumber technicians two to one, every algorithm covers exactly 50%
(capacity is the limit), so the difference moves to *which* jobs get served and
how far people drive: Hungarian drove 14% less than Greedy (645 vs 747 km) and
served more high-value work.

### 2. With multi-job routes, the scarce resource decides the winner

Real technicians do several jobs a day. Here Hungarian runs in rounds (each
round gives every technician at most one more job), which is optimal within a
round but still sequential across rounds. That changes the picture:

- **Light and busy days: Regret insertion wins most often** (13 and 12 of 20).
  On these days the binding constraint is skills and time windows, not raw
  capacity. Regret asks "which job loses most if it waits?" and serves jobs with
  few options first. The clearest example is a job that needs high-voltage work:
  if only one technician has that skill, Greedy may already have spent their day
  on routine jobs anyone could do. `test_regret_protects_the_scarce_specialist`
  reproduces this, and the UI shows it in the default scenario (seed 7, job J002:
  only Regret serves it, with the explanation "only one technician could still
  take it").
- **Hungarian is weakest on the light day** (highest driving, 1090 km). Its
  first round gives every technician a job at once, even technicians who are
  far from everything, because the matching must be one-to-one and every
  pairing earns a reward. That early spreading is optimal for round one and
  poor for the day as a whole.

### 3. Under heavy overload, global matching wins again

With 120 jobs for 20 technicians, Hungarian won 14 of 20 seeds and drove 20% less
than Greedy (1990 vs 2487 km). When demand far exceeds supply, the key decision
is *which* subset of jobs to serve, and each round's matching chooses that
subset globally. Protecting individual hard jobs (Regret's strength) matters
less when most jobs will go unserved anyway.

### 4. Priority weighting works

Critical coverage is nearly identical across algorithms in every scenario,
because the reward for a critical job outweighs any realistic travel saving.
The remaining critical misses are infeasible for everyone: no technician has
the skill, or none can reach the site inside its window
(`test_critical_jobs_win_when_capacity_is_short` checks the trade-off directly).

### 5. Runtime is not a deciding factor at this scale

All three solve 120 jobs in well under a second. Greedy is fastest. Hungarian
costs O(n^3) per round. Regret would be the slowest (it re-scores every waiting
job at every step), so it caches insertion costs and only recomputes the one
route that changed after each assignment.

## When to use which

| Situation | Best fit | Why |
|---|---|---|
| Jobs arrive one at a time and need an instant answer | Greedy | No future knowledge to exploit; simple and fast to explain |
| A batch of jobs, roughly one per technician (e.g. morning emergency dispatch) | Hungarian | Provably optimal for one-to-one assignment |
| A full day with scarce skills or tight windows | Regret insertion | Serves hard-to-place jobs before easy ones use up the scarce people |
| Demand far above capacity | Hungarian (batch rounds) | Picks which jobs to serve globally and cuts driving the most |

The general lesson: the difference between local and global decisions matters
most when resources are contested. With plenty of slack, all three produce
similar plans; as supply tightens, *what is scarce* (people in general, or
specific skills) decides which strategy wins.

## Limitations and next steps

- **Not a full routing optimum.** Multi-job routing is a vehicle routing
  problem with time windows, which is NP-hard. A next step is local search on
  top of any of these starting plans (moving or swapping jobs between routes),
  or a solver like Google OR-Tools.
- **Static day.** Real dispatch is dynamic: jobs arrive during the day and
  started jobs are fixed. The engine could re-plan with completed and
  in-progress stops frozen.
- **Straight-line distances.** Travel uses great-circle distance times a road
  factor. A local OSRM server would give real road times and stay free.
- **Fixed durations.** Job durations are certain here. An ML model trained on
  historical jobs could predict durations (and their spread), and the planner
  could add buffers for uncertain jobs.
- **Fairness is measured, not optimized.** Workload spread is reported but not
  part of the objective; it could become a soft constraint.
