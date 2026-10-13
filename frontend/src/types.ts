// Mirrors backend/app/models.py
export type Priority = 1 | 2 | 3;

export interface Location { lat: number; lon: number }

export interface Technician {
  id: string; name: string; home: Location; skills: string[];
  shift_start: number; shift_end: number; max_jobs: number;
}

export interface Job {
  id: string; site: string; location: Location; required_skills: string[];
  window_start: number; window_end: number; duration: number; priority: Priority;
}

export interface Scenario {
  technicians: Technician[]; jobs: Job[]; speed_kmh?: number; road_factor?: number;
}

export interface Weights {
  travel_km: number; idle_minute: number; overqualified_skill: number;
  reward_normal: number; reward_high: number; reward_critical: number;
}

export interface Stop { job_id: string; arrival: number; start: number; end: number; travel_km: number; wait: number }
export interface Route { technician_id: string; stops: Stop[]; return_km: number }
export interface Assignment {
  job_id: string; technician_id: string; sequence: number;
  arrival: number; start: number; end: number; travel_km: number;
}
export interface Explanation {
  job_id: string; assigned_to: string | null; summary: string;
  cost: number | null; runner_up: string | null; runner_up_cost: number | null;
  rejected: Record<string, number>;
}
export interface Metrics {
  jobs_total: number; jobs_assigned: number; coverage_pct: number; critical_coverage_pct: number;
  priority_weighted_coverage_pct: number; total_travel_km: number; travel_km_per_job: number;
  avg_wait_min: number; utilization_pct: number; workload_std: number; objective: number; runtime_ms: number;
}
export interface Solution {
  algorithm: string; assignments: Assignment[]; routes: Route[]; unassigned: string[];
  explanations: Explanation[]; metrics: Metrics;
}
export interface AlgorithmInfo { key: string; name: string; description: string }
